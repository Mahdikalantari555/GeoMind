"""Planetary Computer Landsat Fetcher for METRIC ETa model.

This module provides functionality to fetch Landsat scenes directly from
Microsoft Planetary Computer's STAC API at runtime.
"""

import contextlib
import hashlib
import json
import logging
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import numpy as np
import rasterio
import requests
from pyproj import Transformer
from pystac_client import Client
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .errors import (
    AuthenticationError,
    DownloadError,
    GeometryError,
    NoSceneFoundError,
    PartialDataError,
)

# No import-time mutation of numpy/pandas/PROJ_LIB: those global patches were
# only needed by the retired stackstac path. Downloads use rasterio windowing
# (and GDAL for S1), so the process environment is left untouched (D-048).

logger = logging.getLogger(__name__)

# Bounded parallelism for per-asset downloads (D-037).
MAX_PARALLEL_DOWNLOADS = 4

# Bands whose values are bitmasks / class labels: nearest resampling, no
# reflectance scaling, excluded from the valid-pixel coverage check.
QA_BANDS = frozenset({"qa_pixel", "qa60", "scl"})


def _sha256_file(path: Path) -> str:
    """Stream a file through SHA-256 without loading it into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finalize_band(partial: Path, final: Path, band: str, manifest: dict[str, str]) -> Path:
    """Verify a written band, record its digest and atomically rename it."""
    manifest[band] = _sha256_file(partial)
    partial.replace(final)
    return final


def _fetch_bands_parallel(
    asset_keys: list[str],
    worker: Callable[[str], str | None],
    max_workers: int = MAX_PARALLEL_DOWNLOADS,
) -> list[str]:
    """Run per-asset downloads with a bounded thread pool, preserving order."""
    results: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(asset_keys)))) as pool:
        futures = {pool.submit(worker, key): key for key in asset_keys}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:  # surfaced by the caller's integrity check
                logger.warning(f"Band {key} failed: {exc}")
                results[key] = None
    downloaded: list[str] = []
    for key in asset_keys:
        value = results[key]
        if value is not None:
            downloaded.append(value)
    return downloaded


def _load_manifest(scene_dir: Path) -> dict[str, str]:
    """Load the per-scene SHA-256 manifest so downloads resume across processes."""
    manifest_path = scene_dir / ".bands.sha256.json"
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _save_manifest(scene_dir: Path, manifest: dict[str, str]) -> None:
    manifest_path = scene_dir / ".bands.sha256.json"
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)


def _require_bands(item_id: str, downloaded: dict[str, Path], required: list[str]) -> None:
    """Fail a scene that is missing any required band (D-036)."""
    missing = [band for band in required if band not in downloaded]
    if not missing:
        return
    for path in downloaded.values():
        with contextlib.suppress(OSError):
            path.unlink()
    raise PartialDataError(
        f"Scene {item_id} is incomplete",
        missing_bands=missing,
        available_bands=list(downloaded),
    )


def _coverage_ratio(path: Path, qa_path: Path | None = None) -> float:
    """Valid-pixel fraction from the raster mask/nodata and optional QA bits.

    Replaces the ``arr > 0`` heuristic (D-047): nodata is taken from the
    raster itself, and QA/shadow pixels are excluded when a QA band is present.
    """
    with rasterio.open(path) as src:
        valid = src.read_masks(1) > 0
        data = src.read(1)
        if src.nodata is not None:
            valid = valid & (data != src.nodata)
    if qa_path is not None and qa_path.is_file():
        # Lazy import keeps the io layer free of preprocess import cycles.
        from ..preprocess.cloud_mask import CloudMasker

        with rasterio.open(qa_path) as qa_src:
            qa_data = qa_src.read(1)
            if qa_path.stem == "scl":
                valid = valid & CloudMasker.valid_from_scl(qa_data)
            else:
                valid = valid & CloudMasker.valid_from_qa(qa_data)
    total = int(valid.size)
    return float(np.count_nonzero(valid)) / total if total else 1.0


def _enforce_coverage(
    item_id: str,
    paths: list[Path],
    min_coverage_ratio: float,
    qa_path: Path | None = None,
) -> None:
    """Delete a scene whose valid-pixel fraction falls below the threshold."""
    ratio = min(_coverage_ratio(path, qa_path) for path in paths)
    logger.info(f"Valid coverage for {item_id}: {ratio:.3f}")
    if ratio < min_coverage_ratio:
        for path in paths:
            with contextlib.suppress(OSError):
                path.unlink()
        raise DownloadError(
            f"Scene {item_id} has insufficient valid pixel coverage "
            f"({ratio:.1%} < {min_coverage_ratio:.1%})"
        )


def _item_assets(item: Any) -> dict[str, Any]:
    """Return a STAC item's asset mapping, tolerating partial test doubles."""
    from collections.abc import Mapping

    assets = getattr(item, "assets", None)
    if isinstance(assets, Mapping):
        return {str(key): value for key, value in assets.items()}
    return {}


def _raster_band_scaling(item: Any, mapping: dict[str, str]) -> dict[str, dict[str, float]]:
    """Extract STAC ``raster:bands`` scale/offset per internal band name."""
    scaling: dict[str, dict[str, float]] = {}
    for internal, asset_key in mapping.items():
        asset = _item_assets(item).get(asset_key)
        props = getattr(asset, "properties", None) or {}
        bands = props.get("raster:bands") or []
        if not isinstance(bands, list) or not bands:
            continue
        first = bands[0]
        if not isinstance(first, dict):
            continue
        scale, offset = first.get("scale"), first.get("offset")
        if scale is not None and offset is not None:
            scaling[internal] = {"scale": float(scale), "offset": float(offset)}
    return scaling


def _preview_href(item: Any) -> str | None:
    """Pick a quicklook href from a STAC item, if the provider supplies one."""
    assets = _item_assets(item)
    for key in ("rendered_preview", "thumbnail", "preview", "overview"):
        asset = assets.get(key)
        if asset is not None:
            href = getattr(asset, "href", None)
            if isinstance(href, str) and href:
                return href
    return None


def _asset_hrefs(item: Any) -> dict[str, str]:
    """Map all named STAC assets to their hrefs (used for band selection)."""
    result: dict[str, str] = {}
    for key, asset in _item_assets(item).items():
        href = getattr(asset, "href", None)
        if isinstance(href, str) and href:
            result[str(key)] = href
    return result


# Band mapping for MPC STAC assets - matches LandsatReader.DEFAULT_BAND_MAPPING
MPC_BAND_MAPPING = {
    'blue': 'blue',
    'green': 'green',
    'red': 'red',
    'nir08': 'nir08',
    'swir16': 'swir16',
    'swir22': 'swir22',
    'lwir11': 'lwir11',
    'qa_pixel': 'qa_pixel',
}

# Required bands for METRIC processing
REQUIRED_BANDS = ['blue', 'green', 'red', 'nir08', 'swir16', 'swir22', 'lwir11', 'qa_pixel']

# Sentinel-2 specific band mapping for MPC STAC assets
SENTINEL_BAND_MAPPING = {
    'blue': 'B02',
    'green': 'B03',
    'red': 'B04',
    'nir08': 'B08',
    'swir16': 'B11',
    'swir22': 'B12',
    'qa60': 'QA60',
    'scl': 'SCL'
}

# Required bands for Sentinel-2 METRIC processing
SENTINEL_REQUIRED_BANDS = ['blue', 'green', 'red', 'nir08', 'swir16', 'swir22', 'qa60', 'scl']


class PlanetaryComputerLandsatFetcher:
    """Fetcher for Landsat scenes from Microsoft Planetary Computer.

    This class handles authentication, searching, and downloading Landsat
    Collection 2 Level-2 scenes from Planetary Computer's STAC API.

    The fetcher downloads bands as GeoTIFF files clipped to the ROI,
    and generates MTL.json metadata files compatible with METRIC processing.

    Attributes:
        collection: STAC collection ID (default: landsat-c2-l2)
        bands: List of band names to fetch
        max_cloud_cover: Maximum cloud cover percentage (0-100)
        source_crs: CRS of input ROI geometry (default: EPSG:4326 for WGS84 lat/lon).
                   If your ROI is in a different CRS (e.g., UTM), specify it here
                   and the fetcher will transform it to WGS84 for STAC queries.
    """

    # Planetary Computer STAC endpoint
    STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

    # Internal band name -> STAC asset key. Subclasses override this hook so
    # band validation and resolution share one source of truth.
    BAND_MAPPING: dict[str, str] = MPC_BAND_MAPPING

    def __init__(
        self,
        collection: str = "landsat-c2-l2",
        bands: list[str] | None = None,
        max_cloud_cover: float = 70.0,
        source_crs: str = "EPSG:4326",
        cache_dir: str | None = None,
        use_cache: bool = True
    ) -> None:
        """Initialize the fetcher.

        Args:
            collection: STAC collection ID (default: landsat-c2-l2)
            bands: List of band names to fetch (default: standard METRIC bands)
            max_cloud_cover: Maximum cloud cover percentage (0-100)
            source_crs: CRS of input ROI geometry (default: EPSG:4326 for WGS84 lat/lon).
                       If your ROI is in a different CRS (e.g., UTM), specify it here
                       and the fetcher will transform it to WGS84 for STAC queries.
        """
        self.collection = collection
        self.bands = bands or REQUIRED_BANDS.copy()
        self.max_cloud_cover = max_cloud_cover
        self.source_crs = source_crs
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.use_cache = use_cache

        # Validate bands against the subclass hook (Landsat/S2/S1).
        for band in self.bands:
            if band not in self.BAND_MAPPING:
                raise ValueError(
                    f"Unknown band: {band}. Supported bands: {list(self.BAND_MAPPING.keys())}"
                )

        self.client: Client | None = None
        self.band_hashes: dict[str, str] = {}

    def _catalog(self) -> Client:
        """Connect only for a catalog operation; local cache and geometry need no network."""
        if self.client is not None:
            return self.client
        try:
            self.client = Client.open(self.STAC_API_URL)
            logger.info(f"Connected to Planetary Computer STAC API: {self.STAC_API_URL}")
            return self.client
        except Exception as e:
            logger.error(f"Failed to connect to STAC API: {e}")
            raise AuthenticationError(f"Failed to connect to STAC API: {e}") from e

    @contextmanager
    def _catalog_session(self) -> Iterator[Any]:
        """Yield the STAC client and close its HTTP session on exit (D-049)."""
        client = self._catalog()
        try:
            yield client
        finally:
            stac_io = getattr(client, "_stac_io", None)
            session = getattr(stac_io, "session", None)
            if session is not None and hasattr(session, "close"):
                session.close()
            # A closed client must not be returned by a later _catalog() call.
            self.client = None

    def _catalog_items(self, search_params: dict[str, Any]) -> list[Any]:
        """Run a STAC search inside the managed catalog session."""
        with self._catalog_session() as client:
            return list(client.search(**cast(Any, search_params)).items())

    def fetch_scenes(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime],
        output_dir: str,
        min_cloud_cover: float = 0.0,
        resolution: float = 30.0,
        sort_by: str = 'date',
        min_coverage_ratio: float = 0.9,
        selected_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch and download Landsat scenes clipped to ROI.

        Args:
            roi_geometry: GeoJSON geometry dict or shapely geometry for the area of interest
            date_range: Tuple of (start_date, end_date) - both inclusive
            output_dir: Directory to save output files
            min_cloud_cover: Minimum cloud cover percentage (0-100) to filter out clear scenes
            resolution: Output resolution in meters (default: 30.0 for Landsat)
            sort_by: Sort results by 'date' (default) or 'cloud_cover'
            min_coverage_ratio: Minimum valid pixel coverage ratio within the
                ROI clip (default: 0.9 = 90% — must stay below 1.0 because real
                Landsat scenes carry nodata fill at footprint edges and along
                gaps; requiring 100% rejects every real scene)

        Returns:
            List of dicts with scene info and file paths:
                {
                    "scene_id": str,
                    "date": str (YYYY-MM-DD),
                    "cloud_cover": float,
                    "path": str,
                    "row": str,
                    "directory": str,
                    "bands_downloaded": int,
                    "mtl_file": str (path),
                    "band_files": Dict[str, Path] (band name -> file path)
                }
            Sorted by date (ascending) or cloud cover (ascending) based on sort_by param

        Raises:
            NoSceneFoundError: No suitable scenes found
            AuthenticationError: MPC authentication failed
            DownloadError: Band download failed for one or more scenes
            GeometryError: Invalid ROI geometry
        """
        # Normalize ROI geometry
        roi_geometry = self._normalize_geometry(roi_geometry)
        roi_bbox = list(roi_geometry.bounds)

        # Normalize dates
        start_date, end_date = self._normalize_dates(date_range)

        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Search using bbox
        items = self._search_scenes_by_bbox(roi_bbox, start_date, end_date, min_cloud_cover)

        # Filter for full ROI coverage
        full_coverage_items = self._filter_full_coverage(roi_bbox, items)

        if not full_coverage_items:
            raise NoSceneFoundError("No scenes found with full ROI coverage")
        if sort_by == 'cloud_cover':
            full_coverage_items.sort(key=lambda item: item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 100.0)))
        else:
            full_coverage_items.sort(key=lambda item: item.datetime or datetime.min)

        logger.info(f"Found {len(full_coverage_items)} qualifying scenes with full coverage")

        # Restrict to the scenes the caller actually selected (if any).
        if selected_ids is not None:
            wanted = {str(sid) for sid in selected_ids}
            full_coverage_items = [item for item in full_coverage_items if str(item.id) in wanted]
            if not full_coverage_items:
                logger.info("None of the selected scenes matched the catalog; nothing to download")
                return []

        # Download each scene
        results: list[dict[str, Any]] = []
        for item in full_coverage_items:
            scene_date = item.properties["datetime"][:10]
            path = item.properties.get('landsat:wrs_path')
            row = item.properties.get('landsat:wrs_row')

            # Create scene directory
            scene_dir = output_path / f"landsat_{scene_date.replace('-', '')}_{path}_{row}"
            scene_dir.mkdir(parents=True, exist_ok=True)

            # Skip download if scene already exists on disk
            existing = self._find_existing_scene(scene_dir)
            if existing is not None:
                downloaded_files, mtl_path = existing
                logger.info(f"Scene {item.id} already downloaded, skipping: {scene_dir}")
            else:
                # Download and clip bands
                try:
                    downloaded_files = self.download_and_clip_bands(
                        item, roi_bbox, scene_dir, resolution, min_coverage_ratio
                    )
                except DownloadError as e:
                    # Scene has insufficient coverage, try next scene
                    logger.warning(f"Skipping scene {item.id}: {e}")
                    # Clean up the scene directory
                    try:
                        for f in scene_dir.iterdir():
                            if f.is_file():
                                f.unlink()
                        scene_dir.rmdir()
                    except Exception:
                        pass
                    continue

                # Create MTL.json
                mtl_path = self._create_mtl_metadata(item, scene_dir)

            results.append({
                "scene_id": item.id,
                "date": scene_date,
                "cloud_cover": item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 0.0)),
                "path": path,
                "row": row,
                "directory": str(scene_dir),
                "bands_downloaded": len(downloaded_files),
                "mtl_file": str(mtl_path),
                "band_files": downloaded_files
            })

        if not results:
            raise NoSceneFoundError(
                "No scenes found with sufficient valid pixel coverage. "
                f"Tried {len(full_coverage_items)} scene(s) but all had coverage < {min_coverage_ratio * 100:.0f}%"
            )

        return results

    def _find_existing_scene(self, scene_dir: Path) -> tuple[dict[str, Path], Path] | None:
        """Check if a scene was already downloaded.

        A scene counts as complete when its directory contains all
        required band .tif files plus an MTL.json metadata file.

        Args:
            scene_dir: Scene output directory to inspect

        Returns:
            (band_files, mtl_path) tuple if complete, else None
        """
        if not scene_dir.is_dir():
            return None
        band_files = {}
        for band in self.bands:
            band_path = scene_dir / f"{band}.tif"
            if not band_path.is_file():
                return None
            band_files[band] = band_path
        # Only MTL*.json marks a complete scene; other JSON files (e.g. a
        # partial download manifest) must not make an incomplete scene cache-hit.
        mtl_candidates = list(scene_dir.glob("MTL*.json"))
        if not mtl_candidates:
            return None
        return band_files, mtl_candidates[0]

    def search_scenes(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime]
    ) -> list[dict[str, Any]]:
        """Search for available scenes (returns metadata only, no download).

        Args:
            roi_geometry: GeoJSON geometry dict or shapely geometry
            date_range: Tuple of (start_date, end_date) as strings or datetime

        Returns:
            List of scene metadata dictionaries
        """
        roi_geometry = self._normalize_geometry(roi_geometry)
        start_date, end_date = self._normalize_dates(date_range)

        # Get bbox from ROI geometry
        bbox = list(roi_geometry.bounds)

        # Search with bbox
        search_params = {
            "collections": [self.collection],
            "bbox": bbox,
            "datetime": f"{start_date.isoformat()}/{end_date.isoformat()}",
            "limit": 100,
        }

        try:
            items = self._catalog_items(search_params)
        except Exception as e:
            logger.error(f"STAC search failed: {e}")
            raise

        # Convert to metadata dicts
        results: list[dict[str, Any]] = []
        for item in items:
            cloud_cover = item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 0.0))
            if cloud_cover <= self.max_cloud_cover:
                results.append({
                    'id': item.id,
                    'datetime': item.datetime,
                    'cloud_cover': cloud_cover,
                    'platform': item.properties.get('platform'),
                    'bbox': item.bbox,
                    'geometry': item.geometry,
                    'preview_url': _preview_href(item),
                    'assets': _asset_hrefs(item),
                    'coverage': self._coverage_label(bbox, item),
                })

        return results

    def get_scene_count(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime]
    ) -> int:
        """Get count of available scenes without downloading.

        Args:
            roi_geometry: GeoJSON geometry dict or shapely geometry
            date_range: Tuple of (start_date, end_date) as strings or datetime

        Returns:
            Number of scenes that match the criteria (including partial overlaps)
        """
        # Catalog failures must propagate as typed errors, never become "0 scenes".
        return len(self.search_scenes(roi_geometry, date_range))

    def _search_scenes_by_bbox(
        self,
        bbox: list[float],
        start_date: datetime,
        end_date: datetime,
        min_cloud_cover: float
    ) -> list[Any]:
        """Internal method to search STAC API for scenes using bbox.

        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat] in WGS84
            start_date: Start datetime
            end_date: End datetime
            min_cloud_cover: Minimum cloud cover percentage

        Returns:
            List of STAC items that intersect with bbox and meet cloud cover criteria
        """
        # Build search parameters
        search_params = {
            "collections": [self.collection],
            "bbox": bbox,
            "datetime": f"{start_date.isoformat()}/{end_date.isoformat()}",
            "limit": 100,
        }

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception_type(requests.RequestException),
            reraise=True,
        )
        def _do_search() -> list[Any]:
            try:
                return self._catalog_items(search_params)
            except Exception as exc:
                logger.error(f"STAC search request failed: {exc}")
                raise AuthenticationError(f"STAC search failed: {exc}") from exc

        items = _do_search()

        # Filter by cloud cover - ensure we don't exceed max_cloud_cover
        filtered = []
        for item in items:
            cloud_cover = item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 0.0))
            if cloud_cover <= self.max_cloud_cover:
                filtered.append(item)
            else:
                logger.debug(f"Scene {item.id} filtered out: cloud cover {cloud_cover}% > {self.max_cloud_cover}%")

        logger.info(f"Found {len(filtered)} scenes with cloud cover <= {self.max_cloud_cover}%")
        return filtered

    def _filter_full_coverage(
        self,
        roi_bbox: list[float],
        items: list[Any],
    ) -> list[Any]:
        """Filter items to only those that fully contain the ROI geometry.

        This method provides an initial filter based on scene footprint geometry.
        Note: Final validation of actual pixel coverage happens AFTER downloading
        in the download_and_clip_bands method.

        Args:
            roi_bbox: [min_lon, min_lat, max_lon, max_lat] in WGS84
            items: List of STAC items

        Returns:
            List of items where ROI bbox intersects with scene footprint
        """
        from shapely.geometry import shape

        roi_box = box(roi_bbox[0], roi_bbox[1], roi_bbox[2], roi_bbox[3])
        candidates = []

        for item in items:
            # Use the scene footprint geometry
            try:
                scene_footprint = shape(item.geometry)
            except Exception as e:
                logger.warning(f"Could not parse scene geometry for {item.id}: {e}")
                continue

            # Check if there's any intersection (looser filter at this stage)
            # Final validation will be done after download
            if roi_box.intersects(scene_footprint):
                candidates.append(item)
            else:
                logger.debug(f"Scene {item.id} does not intersect with ROI at all")

        logger.info(f"Initial filter: {len(candidates)} scenes intersect with ROI (final validation after download)")

        return candidates

    def _coverage_label(self, roi_bbox: list[float], item: Any) -> str:
        """Classify search coverage so callers can choose (D-038).

        Final pixel-level validation still happens after download; this label
        distinguishes a footprint that fully covers the ROI from one that only
        intersects it.
        """
        from shapely.geometry import shape

        try:
            footprint = shape(item.geometry)
            return "full" if footprint.covers(box(*roi_bbox)) else "partial"
        except Exception:
            return "partial"

    def _write_windowed_band(
        self,
        asset_href: str,
        bbox: list[float],
        out_path: Path,
        size: float,
        is_qa: bool = False,
    ) -> Path:
        """Read a ROI window at ``size`` metres and write a tiled COG.

        ``out_shape`` honours the requested resolution while ``window_transform``
        is rescaled to match (D-045). QA/SCL bands use nearest-neighbour.
        Overviews and tiling make the bands COG-compliant (P-077).
        """
        from rasterio.windows import from_bounds

        partial = out_path.with_name(out_path.name + ".partial")
        with rasterio.open(asset_href) as src:
            # Clip in the scene's own CRS (the three-corner envelope fix).
            bounds = self._bounds_in_crs(bbox, src.crs)
            window = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], src.transform)
            src_res = abs(src.transform.a) or float(size)
            full_w = max(1, int(round(window.width)))
            full_h = max(1, int(round(window.height)))
            out_w = max(1, min(full_w, int(round(full_w * src_res / float(size)))))
            out_h = max(1, min(full_h, int(round(full_h * src_res / float(size)))))
            resampling = (
                rasterio.enums.Resampling.nearest
                if is_qa
                else rasterio.enums.Resampling.bilinear
            )
            data = src.read(1, window=window, out_shape=(out_h, out_w), resampling=resampling)
            out_transform = src.window_transform(window) * rasterio.Affine.scale(
                window.width / out_w, window.height / out_h
            )
            nodata_val = src.nodata
            crs = src.crs

        with rasterio.open(
            partial,
            'w',
            driver='GTiff',
            height=out_h,
            width=out_w,
            count=1,
            dtype=data.dtype,
            crs=crs,
            transform=out_transform,
            compress='lzw',
            nodata=nodata_val,
            tiled=True,
        ) as dst:
            dst.write(data, 1)
            dst.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.nearest)
            dst.update_tags(ns='rio_overview', resampling='nearest')
        return _finalize_band(partial, out_path, out_path.stem, self.band_hashes)

    def _download_with_retry(
        self,
        item: Any,
        asset_key: str,
        href: str,
        write_band: Callable[[str, Path, bool], None],
        out_path: Path,
        is_qa: bool,
        attempts: int = 3,
    ) -> None:
        """Download one band with per-band retry/timeout and re-signing (D-046)."""
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                write_band(href, out_path, is_qa)
                logger.info(f"Saved band {asset_key} -> {out_path}")
                return
            except Exception as exc:
                last = exc
                logger.warning(f"Band {asset_key} attempt {attempt + 1} failed: {exc}")
                if attempt < attempts - 1:
                    try:
                        import planetary_computer

                        href = planetary_computer.sign(item).assets[asset_key].href
                    except Exception:
                        pass
                    time.sleep(0.5 * (2**attempt))
        raise DownloadError(
            f"Failed to download band {asset_key} after {attempts} attempts",
            band_name=asset_key,
        ) from last

    def download_and_clip_bands(
        self,
        item: Any,
        bbox: list[float],
        output_dir: Path,
        resolution: float = 30.0,
        min_coverage_ratio: float = 0.55
    ) -> dict[str, Path]:
        """Download ROI-clipped Landsat bands with integrity checks.

        Each asset is written to ``.partial``, hashed, then atomically renamed.
        Bands are fetched with bounded parallelism (default 4), retried with
        re-signing, and a scene missing any required band raises
        :class:`PartialDataError` instead of being registered as complete.
        """
        try:
            import planetary_computer

            signed_item = planetary_computer.sign(item)
            logger.debug(f"Successfully signed item: {item.id}")
        except Exception as e:
            logger.error(f"Failed to sign item {item.id}: {e}")
            raise AuthenticationError(f"MPC authentication failed for item {item.id}: {e}") from e

        self.band_hashes = _load_manifest(output_dir)
        asset_keys = [b for b in self.bands if b in _item_assets(signed_item)]
        if not asset_keys:
            raise DownloadError(f"No required bands found in item {item.id}")

        def write_band(href: str, out_path: Path, is_qa: bool) -> None:
            self._write_windowed_band(href, bbox, out_path, resolution, is_qa)

        def worker(asset_key: str) -> str | None:
            out_path = output_dir / f"{asset_key}.tif"
            if out_path.is_file() and self.band_hashes.get(asset_key) == _sha256_file(out_path):
                logger.info(f"Reusing verified band {asset_key}")
                return asset_key
            partial = out_path.with_name(out_path.name + ".partial")
            if partial.is_file() and asset_key in self.band_hashes:
                _finalize_band(partial, out_path, asset_key, self.band_hashes)
                return asset_key
            try:
                href = signed_item.assets[asset_key].href
                self._download_with_retry(item, asset_key, href, write_band, out_path, asset_key in QA_BANDS)
                return asset_key
            except Exception as exc:
                logger.warning(f"Failed to download band {asset_key}: {exc}", exc_info=True)
                with contextlib.suppress(OSError):
                    partial.unlink(missing_ok=True)
                return None

        _fetch_bands_parallel(asset_keys, worker)

        downloaded = {
            band: output_dir / f"{band}.tif"
            for band in asset_keys
            if (output_dir / f"{band}.tif").is_file()
        }
        _require_bands(item.id, downloaded, self.bands)

        qa_path = downloaded.get("qa_pixel")
        reflectance = [p for name, p in downloaded.items() if name not in QA_BANDS]
        _enforce_coverage(
            item.id, reflectance or list(downloaded.values()), min_coverage_ratio, qa_path
        )
        _save_manifest(output_dir, self.band_hashes)
        return downloaded

    def _create_mtl_metadata(self, item: Any, output_dir: Path) -> Path:
        """Create MTL.json from STAC item properties.

        Args:
            item: STAC item
            output_dir: Directory to save MTL.json

        Returns:
            Path to the created MTL.json file
        """
        scene_id = item.id
        scene_date = item.properties["datetime"][:10]
        cloud_cover = item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 0.0))
        path = item.properties.get('landsat:wrs_path')
        row = item.properties.get('landsat:wrs_row')
        sun_elevation = item.properties.get("view:sun_elevation")
        sun_azimuth = item.properties.get("view:sun_azimuth")

        # Derive platform and instruments from the Landsat scene_id prefix
        # (e.g. LC08 -> landsat-8 / oli_tirs; LC09 -> landsat-9 / oli_tirs)
        platform = "unknown"
        instruments = []
        if scene_id:
            prefix = scene_id.split('_')[0].upper()
            if prefix in ("LC08", "LO08"):
                platform = "landsat-8"
                instruments = ["oli", "tirs"]
            elif prefix in ("LC09", "LO09"):
                platform = "landsat-9"
                instruments = ["oli", "tirs"]
            elif prefix in ("LC07",):
                platform = "landsat-7"
                instruments = ["etm"]

        # Derive processing level (L2SP/L1TP/...) if present in properties
        correction = item.properties.get("landsat:correction") or item.properties.get("landsat:processing_level")

        # Use the Landsat product scene_id if available
        landsat_scene_id = item.properties.get("landsat:scene_id", scene_id)

        mtl_data = {
            "item_id": scene_id,
            "landsat:scene_id": landsat_scene_id,
            "datetime": scene_date,
            "platform": platform,
            "instruments": instruments,
            "landsat_correction": correction,
            "cloud_cover": cloud_cover,
            "path": path,
            "row": row,
            "sun_elevation": sun_elevation,
            "sun_azimuth": sun_azimuth,
            "geometry": item.geometry,
            "bbox": item.bbox,
            "collection": item.collection_id,
            "properties": item.properties,
            "assets": list(item.assets.keys()),
            "band_scaling": _raster_band_scaling(item, MPC_BAND_MAPPING),
            "band_sha256": dict(self.band_hashes),
        }

        # Add MTL-compatible structure
        mtl_data["METADATA"] = {
            "PRODUCT_METADATA": {
                "LANDSAT_PRODUCT_ID": scene_id,
                "ACQUISITION_DATE": scene_date,
                "WRS Path": str(path).zfill(3) if path else "N/A",
                "WRS Row": str(row).zfill(3) if row else "N/A",
                "CLOUD_COVER": cloud_cover,
            },
            "SUN_PARAMETERS": {
                "SUN_ELEVATION": sun_elevation,
                "SUN_AZIMUTH": sun_azimuth
            }
        }

        mtl_path = output_dir / "MTL.json"
        with open(mtl_path, 'w') as f:
            json.dump(mtl_data, f, indent=2, default=str)

        logger.info(f"Created MTL.json at {mtl_path}")
        return mtl_path

    def _bounds_in_crs(self, bbox: list[float], dst_crs: Any) -> tuple[float, float, float, float]:
        """Project a WGS84 bbox into ``dst_crs`` and return an axis-aligned bound.

        Transforming only the two diagonal corners is wrong: projected space is
        rotated relative to the geographic bbox, so the resulting rectangle can
        miss part of the ROI. Sample every corner plus the edge midpoints and
        take the envelope.
        """
        transformer = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
        lon0, lon1 = bbox[0], bbox[2]
        lat0, lat1 = bbox[1], bbox[3]
        sample_lons = [lon0, (lon0 + lon1) / 2, lon1]
        sample_lats = [lat0, (lat0 + lat1) / 2, lat1]
        xs: list[float] = []
        ys: list[float] = []
        for lat in sample_lats:
            for lon in sample_lons:
                x, y = transformer.transform(lon, lat)
                xs.append(x)
                ys.append(y)
        return (min(xs), min(ys), max(xs), max(ys))

    def _utm_bounds_for_bbox(self, bbox: list[float], utm_epsg: int) -> tuple[float, float, float, float]:
        """Project a WGS84 bbox into a UTM zone and return an axis-aligned bound."""
        return self._bounds_in_crs(bbox, f"EPSG:{utm_epsg}")

    def _get_utm_epsg(self, bbox: list[float]) -> int:
        """Determine UTM EPSG code for a given bbox in WGS84.

        Args:
            bbox: [min_lon, min_lat, max_lon, max_lat] in WGS84

        Returns:
            EPSG code for the appropriate UTM zone
        """
        # Calculate centroid
        lon_center = (bbox[0] + bbox[2]) / 2
        lat_center = (bbox[1] + bbox[3]) / 2

        # UTM zone number
        zone_number = int((lon_center + 180) / 6) + 1

        # Northern or Southern hemisphere
        epsg = 32600 + zone_number if lat_center >= 0 else 32700 + zone_number

        return epsg

    def _normalize_geometry(
        self,
        geometry: dict[str, Any] | BaseGeometry,
        target_crs: str | None = None
    ) -> BaseGeometry:
        """Normalize input geometry to shapely geometry and transform to WGS84.

        Args:
            geometry: GeoJSON dict or shapely geometry in source_crs
            target_crs: Override source CRS detection. If provided, use this CRS.
                       If not provided, will try to detect from geometry or use self.source_crs.

        Returns:
            Shapely geometry in WGS84 (EPSG:4326)

        Raises:
            GeometryError: If geometry is invalid or transformation fails
        """
        from shapely.geometry import shape

        if isinstance(geometry, dict):
            geom_type = geometry.get("type")
            geom_type_lower = geom_type.lower() if isinstance(geom_type, str) else None
            # Handle GeoJSON FeatureCollection -> union of all feature geometries
            if geom_type_lower == "featurecollection":
                features = geometry.get("features", [])
                if not features:
                    raise GeometryError("FeatureCollection has no features")
                geoms = []
                for feat in features:
                    if not isinstance(feat, dict):
                        continue
                    ftype = feat.get("type")
                    ftype_lower = ftype.lower() if isinstance(ftype, str) else None
                    if ftype_lower == "feature":
                        g = feat.get("geometry")
                        if g is None:
                            continue
                        try:
                            geoms.append(shape(g))
                        except Exception as e:
                            raise GeometryError(f"Invalid GeoJSON geometry in Feature: {e}") from e
                    else:
                        # FeatureCollection containing bare geometries (non-standard but handle)
                        try:
                            geoms.append(shape(feat))
                        except Exception as e:
                            raise GeometryError(f"Invalid GeoJSON geometry in FeatureCollection: {e}") from e
                if not geoms:
                    raise GeometryError("FeatureCollection contains no valid geometries")
                geom = unary_union(geoms) if len(geoms) > 1 else geoms[0]
            elif geom_type_lower == "feature":
                g = geometry.get("geometry")
                if g is None:
                    raise GeometryError("Feature has no geometry")
                try:
                    geom = shape(g)
                except Exception as e:
                    raise GeometryError(f"Invalid GeoJSON geometry: {e}") from e
            else:
                # Plain geometry dict (Polygon, MultiPolygon, GeometryCollection, etc.)
                try:
                    geom = shape(geometry)
                except Exception as e:
                    raise GeometryError(f"Invalid GeoJSON geometry: {e}") from e
        elif isinstance(geometry, BaseGeometry):
            geom = geometry
        else:
            raise GeometryError(
                f"Geometry must be dict or shapely geometry, got {type(geometry)}"
            )

        if geom.is_empty:
            raise GeometryError("Geometry is empty")

        # Determine source CRS
        source_crs = target_crs or self.source_crs

        # Try to detect CRS from geometry if it has a CRS (e.g., from GeoJSON with CRS info)
        if target_crs is None and hasattr(geom, 'crs') and geom.crs:
            source_crs = str(geom.crs)
            logger.debug(f"Detected CRS from geometry: {source_crs}")

        # If still not determined, check if bounds are in WGS84 range
        if target_crs is None and source_crs.upper() == "EPSG:4326":
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            # Check if bounds are outside WGS84 range (lon: -180 to 180, lat: -90 to 90)
            if bounds[0] < -180 or bounds[1] < -90 or bounds[2] > 180 or bounds[3] > 90:
                # Bounds are outside WGS84 range, likely in a projected CRS
                logger.warning(f"Geometry bounds {bounds} are outside WGS84 range, attempting to detect UTM zone")
                # Try to determine UTM zone from centroid
                centroid = geom.centroid
                lon, lat = centroid.x, centroid.y
                if lat >= 0:
                    zone = int((lon + 180) / 6) + 1
                    source_crs = f"EPSG:326{zone:02d}"  # Northern hemisphere UTM
                else:
                    zone = int((lon + 180) / 6) + 1
                    source_crs = f"EPSG:327{zone:02d}"  # Southern hemisphere UTM
                logger.info(f"Auto-detected source CRS as {source_crs} based on geometry bounds")

        # Transform to WGS84 if needed
        if source_crs.upper() != "EPSG:4326":
            try:
                transformer = Transformer.from_crs(
                    source_crs, "EPSG:4326", always_xy=True
                )
                geom = shapely_transform(transformer.transform, geom)
                logger.debug(f"Transformed geometry from {source_crs} to WGS84")
            except Exception as e:
                raise GeometryError(
                    f"Failed to transform geometry from {source_crs} to WGS84: {e}"
                ) from e

        return geom

    def _normalize_dates(
        self,
        date_range: tuple[str | datetime, str | datetime]
    ) -> tuple[datetime, datetime]:
        """Normalize date range to datetime objects.

        Args:
            date_range: Tuple of (start_date, end_date) as strings or datetime

        Returns:
            Tuple of (start_datetime, end_datetime)
        """
        start, end = date_range

        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        # Ensure end date includes the full day
        if end.time() == datetime.min.time():
            end = end + timedelta(days=1) - timedelta(seconds=1)

        if start > end:
            raise ValueError(f"Start date {start} is after end date {end}")

        return start, end


class SentinelPlanetaryComputerFetcher(PlanetaryComputerLandsatFetcher):
    """Fetcher for Sentinel-2 scenes from Microsoft Planetary Computer.

    This class handles authentication, searching, and downloading Sentinel-2
    L2A scenes from Planetary Computer's STAC API. It reuses geometry and
    date normalization methods from the parent Landsat fetcher but uses the
    ``sentinel-2-l2a`` STAC collection and maps internal band names
    (blue, green, red, nir08, …) to Sentinel‑2 asset keys (B02, B03, B04, B08, …).
    """

    # Band mapping from internal (METRIC) names to Sentinel‑2 STAC asset keys
    SENTINEL_BAND_MAPPING = {
        'blue': 'B02',
        'green': 'B03',
        'red': 'B04',
        'nir08': 'B08',
        'swir16': 'B11',
        'swir22': 'B12',
        'qa60': 'QA60',
        'scl': 'SCL',
    }
    BAND_MAPPING: dict[str, str] = SENTINEL_BAND_MAPPING

    def __init__(
        self,
        collection: str = "sentinel-2-l2a",
        bands: list[str] | None = None,
        max_cloud_cover: float = 70.0,
        source_crs: str = "EPSG:4326",
    ) -> None:
        # Use internal band names (blue, green, …) as the primary band list.
        required = ['blue', 'green', 'red', 'nir08', 'swir16', 'swir22', 'qa60', 'scl']
        super().__init__(
            collection=collection,
            bands=bands or required,
            max_cloud_cover=max_cloud_cover,
            source_crs=source_crs,
        )

    def search_scenes(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime],
    ) -> list[dict[str, Any]]:
        """Search for available Sentinel-2 scenes.

        Returns metadata dicts with ``id``, ``datetime``, ``cloud_cover``,
        ``platform``, and ``geometry``.
        """
        roi_geometry = self._normalize_geometry(roi_geometry)
        start_date, end_date = self._normalize_dates(date_range)

        bbox = list(roi_geometry.bounds)
        search_params = {
            "collections": [self.collection],
            "bbox": bbox,
            "datetime": f"{start_date.isoformat()}/{end_date.isoformat()}",
            "limit": 100,
        }
        try:
            items = self._catalog_items(search_params)
        except Exception as e:
            logger.error(f"STAC search failed: {e}")
            raise AuthenticationError(f"STAC search failed: {e}") from e

        results: list[dict[str, Any]] = []
        for item in items:
            cloud_cover = item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 0.0))
            if cloud_cover <= self.max_cloud_cover:
                results.append({
                    'id': item.id,
                    'datetime': item.datetime,
                    'cloud_cover': cloud_cover,
                    'platform': item.properties.get('platform'),
                    'bbox': item.bbox,
                    'geometry': item.geometry,
                    'preview_url': _preview_href(item),
                    'assets': _asset_hrefs(item),
                    'coverage': self._coverage_label(bbox, item),
                })
        return results

    def download_and_clip_bands(
        self,
        item: Any,
        bbox: list[float],
        output_dir: Path,
        resolution: float = 10.0,
        min_coverage_ratio: float = 0.55,
    ) -> dict[str, Path]:
        """Download ROI-clipped Sentinel-2 bands with integrity checks."""
        try:
            import planetary_computer

            signed_item = planetary_computer.sign(item)
        except Exception as e:
            raise AuthenticationError(
                f"MPC authentication failed for {item.id}: {e}"
            ) from e

        self.band_hashes = _load_manifest(output_dir)
        available = _item_assets(signed_item)
        pairs = [
            (band, self.BAND_MAPPING[band])
            for band in self.bands
            if band in self.BAND_MAPPING and self.BAND_MAPPING[band] in available
        ]
        if not pairs:
            raise DownloadError(
                f"No required bands found in Sentinel-2 item {item.id}. "
                f"Available assets: {list(available)}"
            )
        asset_to_internal = {asset: internal for internal, asset in pairs}

        def write_band(href: str, out_path: Path, is_qa: bool) -> None:
            self._write_windowed_band(href, bbox, out_path, resolution, is_qa)

        def worker(asset_key: str) -> str | None:
            internal = asset_to_internal[asset_key]
            out_path = output_dir / f"{internal}.tif"
            if out_path.is_file() and self.band_hashes.get(internal) == _sha256_file(out_path):
                logger.info(f"Reusing verified band {internal}")
                return internal
            partial = out_path.with_name(out_path.name + ".partial")
            if partial.is_file() and internal in self.band_hashes:
                _finalize_band(partial, out_path, internal, self.band_hashes)
                return internal
            try:
                self._download_with_retry(
                    item, asset_key, signed_item.assets[asset_key].href,
                    write_band, out_path, internal in QA_BANDS,
                )
                return internal
            except Exception as exc:
                logger.warning(f"Failed to download band {asset_key}: {exc}", exc_info=True)
                with contextlib.suppress(OSError):
                    partial.unlink(missing_ok=True)
                return None

        _fetch_bands_parallel([asset for _, asset in pairs], worker)

        downloaded = {
            internal: output_dir / f"{internal}.tif"
            for internal, _ in pairs
            if (output_dir / f"{internal}.tif").is_file()
        }
        _require_bands(item.id, downloaded, self.bands)

        reflectance = [p for name, p in downloaded.items() if name not in QA_BANDS]
        qa_path = downloaded.get("scl") or downloaded.get("qa60")
        _enforce_coverage(
            item.id, reflectance or list(downloaded.values()), min_coverage_ratio, qa_path
        )
        _save_manifest(output_dir, self.band_hashes)
        return downloaded

    def _create_mtl_metadata(self, item: Any, output_dir: Path) -> Path:
        """Create an MTL.json from Sentinel-2 STAC properties."""
        scene_id = item.id
        scene_date = item.properties["datetime"][:10]
        cloud_cover = item.properties.get('eo:cloud_cover', item.properties.get('cloud_cover', 0.0))
        platform = item.properties.get('platform', 'sentinel-2')
        sensor = item.properties.get('instruments', ['MSI'])[0] if item.properties.get('instruments') else 'MSI'
        sun_elev = item.properties.get("view:sun_elevation")
        sun_az = item.properties.get("view:sun_azimuth")

        mtl_data = {
            "item_id": scene_id,
            "datetime": scene_date,
            "platform": platform,
            "sensor": sensor,
            "processing_level": "L2A",
            "spacecraft": item.properties.get("constellation", "sentinel-2"),
            "cloud_cover": cloud_cover,
            "view:sun_elevation": sun_elev,
            "view:sun_azimuth": sun_az,
            "ggop:mgrs_grid": item.properties.get('mgrs:grid_code'),
            "geometry": item.geometry,
            "bbox": item.bbox,
            "collection": item.collection_id,
            "properties": item.properties,
            "assets": list(item.assets.keys()),
            "band_scaling": _raster_band_scaling(item, SENTINEL_BAND_MAPPING),
            "band_sha256": dict(self.band_hashes),
        }
        mtl_data["METADATA"] = {
            "PRODUCT_METADATA": {
                "PRODUCT_ID": scene_id,
                "ACQUISITION_DATE": scene_date,
                "CLOUD_COVER": cloud_cover,
                "PLATFORM": platform,
                "SENSOR": sensor,
                "PROCESSING_LEVEL": "L2A",
            },
            "SUN_PARAMETERS": {
                "SUN_ELEVATION": sun_elev,
                "SUN_AZIMUTH": sun_az,
            },
        }
        mtl_path = output_dir / "MTL.json"
        with open(mtl_path, 'w') as f:
            json.dump(mtl_data, f, indent=2, default=str)
        logger.info(f"Created Sentinel-2 MTL.json at {mtl_path}")
        return mtl_path

    def fetch_scenes(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime],
        output_dir: str,
        min_cloud_cover: float = 0.0,
        resolution: float = 10.0,
        sort_by: str = "date",
        min_coverage_ratio: float = 0.55,
        selected_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch and download Sentinel-2 scenes from Planetary Computer.

        This overrides the parent's :meth:`fetch_scenes` to use Sentinel-2
        asset keys (B02, B03, …), write MTL.json with Sentinel-2 metadata,
        and name scene directories ``sentinel_<date>``.

        Args:
            roi_geometry: GeoJSON dict or shapely geometry.
            date_range: (start, end) tuple.
            output_dir: Directory for scene sub-directories.
            min_cloud_cover: Minimum cloud cover filter.
            resolution: Output spatial resolution (m).
            sort_by: ``'date'`` or ``'cloud_cover'``.
            min_coverage_ratio: Minimum valid-pixel coverage.

        Returns:
            List of scene metadata dicts.
        """
        roi_geometry = self._normalize_geometry(roi_geometry)
        roi_bbox = list(roi_geometry.bounds)
        start_date, end_date = self._normalize_dates(date_range)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Search using bbox (inherited method uses self.collection)
        items = self._search_scenes_by_bbox(roi_bbox, start_date, end_date, min_cloud_cover)
        full_coverage_items = self._filter_full_coverage(roi_bbox, items)

        if not full_coverage_items:
            raise NoSceneFoundError("No Sentinel-2 scenes found with full ROI coverage")

        if sort_by == "cloud_cover":
            full_coverage_items.sort(key=lambda it: it.properties.get("eo:cloud_cover", it.properties.get("cloud_cover", 100.0)))
        else:
            full_coverage_items.sort(key=lambda it: it.datetime or datetime.min)

        logger.info(f"Found {len(full_coverage_items)} qualifying Sentinel-2 scenes")

        if selected_ids is not None:
            wanted = {str(sid) for sid in selected_ids}
            full_coverage_items = [item for item in full_coverage_items if str(item.id) in wanted]
            if not full_coverage_items:
                logger.info("None of the selected scenes matched the catalog; nothing to download")
                return []

        results: list[dict[str, Any]] = []
        for item in full_coverage_items:
            scene_date = item.datetime.strftime("%Y%m%d") if item.datetime else "unknown"
            # Stable scene-id suffix prevents same-date tiles overwriting each other.
            suffix = hashlib.sha256(str(item.id).encode("utf-8")).hexdigest()[:8]
            scene_dir = output_path / f"sentinel_{scene_date}_{suffix}"
            scene_dir.mkdir(parents=True, exist_ok=True)

            existing = self._find_existing_scene(scene_dir)
            if existing is not None:
                downloaded_files, mtl_path = existing
                logger.info(f"Scene {item.id} already downloaded, skipping: {scene_dir}")
            else:
                try:
                    downloaded_files = self.download_and_clip_bands(
                        item, roi_bbox, scene_dir, resolution, min_coverage_ratio,
                    )
                except DownloadError as e:
                    logger.warning(f"Skipping scene {item.id}: {e}")
                    continue
                mtl_path = self._create_mtl_metadata(item, scene_dir)

            results.append({
                "scene_id": item.id,
                "date": item.datetime.strftime("%Y-%m-%d") if item.datetime else scene_date,
                "cloud_cover": item.properties.get("eo:cloud_cover", item.properties.get("cloud_cover", 0.0)),
                "directory": str(scene_dir),
                "bands_downloaded": len(downloaded_files),
                "mtl_file": str(mtl_path),
                "band_files": downloaded_files,
            })

        if not results:
            raise NoSceneFoundError(
                f"No Sentinel-2 scenes with sufficient coverage. "
                f"Tried {len(full_coverage_items)} scene(s)."
            )
        return results


# ---------------------------------------------------------------------------
# Sentinel-1 (port from GeoDataEngine io/planetary_computer_fetcher.py:1278-1878,
# adapted to strict typing and GeoMind's lazy-catalog/scene-CRS base).
# ---------------------------------------------------------------------------

#: Sentinel-1 GRD polarisations, expressed as their STAC asset keys.
SENTINEL1_POLARIZATIONS: tuple[str, ...] = ("vv", "vh", "hh", "hv")

#: Zero is the GRD nodata marker in the Planetary Computer COGs.
SENTINEL1_NODATA: float = 0.0

#: RTC measurement rasters are float32 gamma-0 with -32768 as provider nodata.
SENTINEL1_RTC_NODATA: float = -32768.0


def _configure_gdal_http() -> Any:
    """Return GDAL configured for signed ``/vsicurl/`` Planetary Computer URLs.

    Without ``GDAL_DISABLE_READDIR_ON_OPEN`` GDAL tries to list the blob
    container over HTTP before opening the object, which stalls on the MPC
    endpoints. The allowed-extensions option stops it probing sibling assets.
    """
    try:
        from osgeo import gdal
    except ImportError as exc:
        raise DownloadError(
            "Sentinel-1 clipping needs the GDAL Python bindings. "
            "Install them with: conda install -c conda-forge gdal"
        ) from exc

    for key, value in {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
        "CPL_VSIL_CURL_USE_HEAD": "NO",
        "GDAL_HTTP_TIMEOUT": "60",
        "GDAL_HTTP_CONNECTTIMEOUT": "20",
    }.items():
        gdal.SetConfigOption(key, value)
    # Raise instead of returning None so a failed warp is a Python exception.
    gdal.UseExceptions()
    return gdal


class Sentinel1PlanetaryComputerFetcher(PlanetaryComputerLandsatFetcher):
    """Fetcher for Sentinel-1 GRD scenes from the Planetary Computer.

    GRD items have no cloud cover (reported as ``None``, never a fabricated
    0 %), their measurement COGs carry a GCP grid instead of a CRS (clipped via
    a GDAL thin-plate-spline warp), and they expose polarisations rather than
    spectral bands.
    """

    BAND_MAPPING: dict[str, str] = {pol: pol for pol in SENTINEL1_POLARIZATIONS}

    #: Preferred polarisations for an interferometric wide-swath scene.
    DEFAULT_POLARIZATIONS: tuple[str, ...] = ("vv", "vh")

    def __init__(
        self,
        collection: str = "sentinel-1-grd",
        bands: list[str] | None = None,
        max_cloud_cover: float = 70.0,
        source_crs: str = "EPSG:4326",
        instrument_mode: str | None = None,
        orbit_direction: str | None = None,
        resolution: float = 10.0,
    ) -> None:
        self.instrument_mode = instrument_mode or None
        self.orbit_direction = orbit_direction or None
        self.resolution = float(resolution)
        super().__init__(
            collection=collection,
            bands=list(bands) if bands else list(self.DEFAULT_POLARIZATIONS),
            max_cloud_cover=max_cloud_cover,
            source_crs=source_crs,
        )

    # -- search --------------------------------------------------------
    def search_scenes(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime],
    ) -> list[dict[str, Any]]:
        """Search GRD scenes, skipping the cloud filter and adding SAR fields."""
        roi_geometry = self._normalize_geometry(roi_geometry)
        start_date, end_date = self._normalize_dates(date_range)
        search_params = {
            "collections": [self.collection],
            "bbox": list(roi_geometry.bounds),
            "datetime": f"{start_date.isoformat()}/{end_date.isoformat()}",
            "limit": 100,
        }
        try:
            items = self._catalog_items(search_params)
        except Exception as exc:
            logger.error(f"STAC search failed: {exc}")
            raise AuthenticationError(f"STAC search failed: {exc}") from exc

        results: list[dict[str, Any]] = []
        for item in items:
            props = item.properties
            mode = props.get("sar:instrument_mode")
            orbit = props.get("sat:orbit_state")
            if self.instrument_mode and mode != self.instrument_mode:
                continue
            if self.orbit_direction and orbit != self.orbit_direction:
                continue
            results.append(
                {
                    "id": item.id,
                    "datetime": item.datetime,
                    # Sentinel-1 has no cloud-cover property at all.
                    "cloud_cover": None,
                    "platform": props.get("platform")
                    or props.get("constellation", "sentinel-1"),
                    "bbox": item.bbox,
                    "geometry": item.geometry,
                    "polarizations": [
                        str(pol).lower() for pol in props.get("sar:polarizations", [])
                    ],
                    "instrument_mode": mode,
                    "orbit_state": orbit,
                    "relative_orbit": props.get("sat:relative_orbit"),
                    "coverage": self._coverage_label(list(roi_geometry.bounds), item),
                }
            )
        return results

    # -- download ------------------------------------------------------
    def download_and_clip_bands(
        self,
        item: Any,
        bbox: list[float],
        output_dir: Path,
        resolution: float = 10.0,
        min_coverage_ratio: float = 0.55,
    ) -> dict[str, Path]:
        """Warp each polarisation to UTM with integrity checks and resume."""
        gdal = _configure_gdal_http()

        try:
            import planetary_computer

            signed_item = planetary_computer.sign(item)
        except Exception as exc:
            raise AuthenticationError(
                f"MPC authentication failed for item {item.id}: {exc}"
            ) from exc

        self.band_hashes = _load_manifest(output_dir)
        asset_keys = [pol for pol in self.bands if pol in _item_assets(signed_item)]
        if not asset_keys:
            raise DownloadError(
                f"No required bands found in Sentinel-1 item {item.id}. "
                f"Available assets: {list(_item_assets(signed_item))}"
            )

        size = float(resolution or self.resolution)

        def write_band(href: str, out_path: Path, _is_qa: bool) -> None:
            self._warp_s1_band(gdal, href, out_path, bbox, size, rtc=False)

        downloaded = self._download_s1_assets(
            item, signed_item, asset_keys, output_dir, write_band
        )
        _require_bands(item.id, downloaded, self.bands)
        _enforce_coverage(
            item.id, list(downloaded.values()), min_coverage_ratio
        )
        _save_manifest(output_dir, self.band_hashes)
        return downloaded

    def _warp_s1_band(
        self,
        gdal: Any,
        href: str,
        out_path: Path,
        bbox: list[float],
        size: float,
        rtc: bool,
    ) -> None:
        """GDAL-warp one polarisation into a tiled COG with overviews."""
        utm_epsg = self._get_utm_epsg(bbox)
        out_crs = f"EPSG:{utm_epsg}"
        transformer = Transformer.from_crs("EPSG:4326", out_crs, always_xy=True)
        min_x, min_y = transformer.transform(bbox[0], bbox[1])
        max_x, max_y = transformer.transform(bbox[2], bbox[3])
        partial = out_path.with_name(out_path.name + ".partial")
        options: dict[str, Any] = {
            "dstSRS": out_crs,
            "outputBounds": (min_x, min_y, max_x, max_y),
            "xRes": size,
            "yRes": size,
            "resampleAlg": "near",
            "dstNodata": SENTINEL1_NODATA,
            "creationOptions": ["COMPRESS=LZW", "TILED=YES"],
        }
        if rtc:
            options["srcNodata"] = SENTINEL1_RTC_NODATA
        else:
            # Thin-plate spline geolocates the GCP grid (GRD only).
            options["tps"] = True
        gdal.Warp(str(partial), f"/vsicurl/{href}", **options)
        dataset = gdal.Open(str(partial), 1)  # GA_Update
        if dataset is not None:
            dataset.BuildOverviews("NEAREST", [2, 4, 8, 16])
            dataset = None
        _finalize_band(partial, out_path, out_path.stem, self.band_hashes)

    def _download_s1_assets(
        self,
        item: Any,
        signed_item: Any,
        asset_keys: list[str],
        output_dir: Path,
        write_band: Callable[[str, Path, bool], None],
    ) -> dict[str, Path]:
        """Bounded-parallel, resumable download of S1 polarisations."""

        def worker(asset_key: str) -> str | None:
            out_path = output_dir / f"{asset_key}.tif"
            if out_path.is_file() and self.band_hashes.get(asset_key) == _sha256_file(out_path):
                return asset_key
            partial = out_path.with_name(out_path.name + ".partial")
            if partial.is_file() and asset_key in self.band_hashes:
                _finalize_band(partial, out_path, asset_key, self.band_hashes)
                return asset_key
            try:
                self._download_with_retry(
                    item, asset_key, signed_item.assets[asset_key].href,
                    write_band, out_path, False,
                )
                return asset_key
            except Exception as exc:
                logger.warning(f"Failed to download band {asset_key}: {exc}")
                with contextlib.suppress(OSError):
                    partial.unlink(missing_ok=True)
                return None

        _fetch_bands_parallel(asset_keys, worker)
        return {
            band: output_dir / f"{band}.tif"
            for band in asset_keys
            if (output_dir / f"{band}.tif").is_file()
        }

    # -- scene folders -------------------------------------------------
    def _scene_dirname(self, item: Any) -> str:
        """``sentinel1_<date>_<asc|desc>`` — one folder per acquisition pass."""
        scene_date = item.datetime.strftime("%Y%m%d") if item.datetime else "unknown"
        orbit = str(item.properties.get("sat:orbit_state", "")).lower()
        tag = {"ascending": "asc", "descending": "desc"}.get(orbit, orbit[:3])
        return f"sentinel1_{scene_date}_{tag}".rstrip("_")

    def _find_existing_scene(self, scene_dir: Path) -> tuple[dict[str, Path], Path] | None:
        """A scene is done when it has MTL metadata and any polarisation."""
        if not scene_dir.is_dir():
            return None
        mtl_candidates = list(scene_dir.glob("MTL*.json"))
        if not mtl_candidates:
            return None
        bands: dict[str, Path] = {
            path.stem: path
            for path in sorted(scene_dir.glob("*.tif"))
            if path.stem.lower() in self.BAND_MAPPING
        }
        if not bands:
            return None
        return bands, mtl_candidates[0]

    # -- metadata ------------------------------------------------------
    def _create_mtl_metadata(self, item: Any, output_dir: Path) -> Path:
        """Write an ``MTL.json`` describing the Sentinel-1 acquisition."""
        props = item.properties
        scene_id = item.id
        scene_date = props.get("datetime", "")[:10]
        pols = [str(pol).lower() for pol in props.get("sar:polarizations", [])]

        mtl_data: dict[str, Any] = {
            "item_id": scene_id,
            "datetime": scene_date,
            "platform": props.get("platform", "sentinel-1"),
            "constellation": props.get("constellation", "Sentinel-1"),
            "sensor": "SAR-C",
            "processing_level": f"L{props.get('s1:processing_level', '1')} GRD",
            "product_identifier": props.get("s1:product_identifier"),
            "polarizations": pols,
            "instrument_mode": props.get("sar:instrument_mode"),
            "orbit_state": props.get("sat:orbit_state"),
            "relative_orbit": props.get("sat:relative_orbit"),
            "absolute_orbit": props.get("sat:absolute_orbit"),
            "resolution": props.get("s1:resolution"),
            "pixel_spacing": props.get("sar:pixel_spacing_range"),
            "looks": {
                "range": props.get("sar:looks_range"),
                "azimuth": props.get("sar:looks_azimuth"),
            },
            "bbox": item.bbox,
            "geometry": item.geometry,
            "collection": item.collection_id,
            "properties": props,
            "assets": list(item.assets.keys()),
            "band_sha256": dict(self.band_hashes),
            "geolocation": {
                "method": "gdal-tps",
                "note": (
                    "GRD COGs carry ground control points instead of a CRS; "
                    "bands were warped from those GCPs with a thin-plate spline."
                ),
            },
        }
        mtl_data["METADATA"] = {
            "PRODUCT_METADATA": {
                "PRODUCT_ID": scene_id,
                "ACQUISITION_DATE": scene_date,
                "PLATFORM": props.get("platform", "sentinel-1"),
                "PROCESSING_LEVEL": "GRD",
                "INSTRUMENT_MODE": props.get("sar:instrument_mode"),
                "ORBIT_STATE": props.get("sat:orbit_state"),
            }
        }

        mtl_path = output_dir / "MTL.json"
        with open(mtl_path, "w") as handle:
            json.dump(mtl_data, handle, indent=2, default=str)
        logger.info(f"Created Sentinel-1 MTL.json at {mtl_path}")
        return mtl_path

    # -- orchestration -------------------------------------------------
    def fetch_scenes(
        self,
        roi_geometry: dict[str, Any] | BaseGeometry,
        date_range: tuple[str | datetime, str | datetime],
        output_dir: str,
        min_cloud_cover: float = 0.0,
        resolution: float = 10.0,
        sort_by: str = "date",
        min_coverage_ratio: float = 0.55,
        selected_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search, then download every selected GRD scene clipped to the ROI."""
        roi_geometry = self._normalize_geometry(roi_geometry)
        roi_bbox = list(roi_geometry.bounds)
        start_date, end_date = self._normalize_dates(date_range)

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        items = self._search_scenes_by_bbox(
            roi_bbox, start_date, end_date, min_cloud_cover
        )
        candidates = self._filter_full_coverage(roi_bbox, items)
        if not candidates:
            raise NoSceneFoundError("No Sentinel-1 scenes found with full ROI coverage")

        # Sentinel-1 has no cloud cover, so both sort keys collapse to date.
        candidates.sort(key=lambda it: it.datetime or datetime.min)
        logger.info(f"Found {len(candidates)} qualifying Sentinel-1 scenes")

        if selected_ids is not None:
            wanted = {str(sid) for sid in selected_ids}
            candidates = [item for item in candidates if str(item.id) in wanted]
            if not candidates:
                logger.info(
                    "None of the selected scenes matched the catalog; nothing to download"
                )
                return []

        results: list[dict[str, Any]] = []
        for item in candidates:
            scene_dir = output_path / self._scene_dirname(item)
            scene_dir.mkdir(parents=True, exist_ok=True)

            existing = self._find_existing_scene(scene_dir)
            if existing is not None:
                downloaded_files, mtl_path = existing
                logger.info(f"Scene {item.id} already downloaded, skipping: {scene_dir}")
            else:
                try:
                    downloaded_files = self.download_and_clip_bands(
                        item,
                        roi_bbox,
                        scene_dir,
                        resolution or self.resolution,
                        min_coverage_ratio,
                    )
                except DownloadError as exc:
                    logger.warning(f"Skipping scene {item.id}: {exc}")
                    for stale in scene_dir.glob("*.tif"):
                        stale.unlink(missing_ok=True)
                    continue
                mtl_path = self._create_mtl_metadata(item, scene_dir)

            results.append(
                {
                    "scene_id": item.id,
                    "date": item.datetime.strftime("%Y-%m-%d") if item.datetime else "",
                    "orbit_state": item.properties.get("sat:orbit_state"),
                    "relative_orbit": item.properties.get("sat:relative_orbit"),
                    "polarizations": list(downloaded_files),
                    "directory": str(scene_dir),
                    "bands_downloaded": len(downloaded_files),
                    "mtl_file": str(mtl_path),
                    "band_files": downloaded_files,
                    "cloud_available": False,
                    "cloud_cover": None,
                }
            )

        if not results:
            raise NoSceneFoundError(
                "No Sentinel-1 scenes with sufficient coverage. "
                f"Tried {len(candidates)} scene(s)."
            )
        return results


class Sentinel1RtcPlanetaryComputerFetcher(Sentinel1PlanetaryComputerFetcher):
    """Fetcher for radiometric terrain-corrected Sentinel-1 (``sentinel-1-rtc``).

    The RTC collection serves the same GRD acquisitions processed to gamma-0
    with the Copernicus DEM GLO-30 and map-projected to UTM. Its COGs carry a
    real CRS (no GCP grid), so the clip is a plain reprojection, not a TPS warp.
    """

    def __init__(
        self,
        collection: str = "sentinel-1-rtc",
        bands: list[str] | None = None,
        max_cloud_cover: float = 70.0,
        source_crs: str = "EPSG:4326",
        instrument_mode: str | None = None,
        orbit_direction: str | None = None,
        resolution: float = 10.0,
    ) -> None:
        super().__init__(
            collection=collection,
            bands=bands,
            max_cloud_cover=max_cloud_cover,
            source_crs=source_crs,
            instrument_mode=instrument_mode,
            orbit_direction=orbit_direction,
            resolution=resolution,
        )

    # -- download ------------------------------------------------------
    def download_and_clip_bands(
        self,
        item: Any,
        bbox: list[float],
        output_dir: Path,
        resolution: float = 10.0,
        min_coverage_ratio: float = 0.55,
    ) -> dict[str, Path]:
        """Plain-reprojection clip of RTC polarisations with integrity checks."""
        gdal = _configure_gdal_http()

        try:
            import planetary_computer

            signed_item = planetary_computer.sign(item)
        except Exception as exc:
            raise AuthenticationError(
                f"MPC authentication failed for item {item.id}: {exc}"
            ) from exc

        self.band_hashes = _load_manifest(output_dir)
        asset_keys = [pol for pol in self.bands if pol in _item_assets(signed_item)]
        if not asset_keys:
            raise DownloadError(
                f"No required bands found in Sentinel-1 RTC item {item.id}. "
                f"Available assets: {list(_item_assets(signed_item))}"
            )

        size = float(resolution or self.resolution)

        def write_band(href: str, out_path: Path, _is_qa: bool) -> None:
            self._warp_s1_band(gdal, href, out_path, bbox, size, rtc=True)

        downloaded = self._download_s1_assets(
            item, signed_item, asset_keys, output_dir, write_band
        )
        _require_bands(item.id, downloaded, self.bands)
        _enforce_coverage(item.id, list(downloaded.values()), min_coverage_ratio)
        _save_manifest(output_dir, self.band_hashes)
        return downloaded

    # -- metadata ------------------------------------------------------
    def _create_mtl_metadata(self, item: Any, output_dir: Path) -> Path:
        """Write ``MTL.json`` for an RTC scene (parent fields + RTC specifics)."""
        mtl_path = super()._create_mtl_metadata(item, output_dir)
        with open(mtl_path) as handle:
            mtl: dict[str, Any] = json.load(handle)

        mtl["processing_level"] = "L1 GRD (RTC gamma-0)"
        mtl["product_identifier"] = (
            item.properties.get("s1:product_identifier") or item.id
        )
        mtl["radiometry"] = {
            "measure": "gamma0",
            "scale": "linear power",
            "provider_nodata": SENTINEL1_RTC_NODATA,
            "output_nodata": SENTINEL1_NODATA,
        }
        mtl["geolocation"] = {
            "method": "provider-rtc",
            "dem": "Copernicus DEM GLO-30",
            "note": (
                "Bands come from the sentinel-1-rtc collection, already "
                "radiometric terrain corrected and map-projected; the clip "
                "is a plain reprojection with no GCP involvement."
            ),
        }
        mtl["METADATA"]["PRODUCT_METADATA"]["PROCESSING_LEVEL"] = "RTC gamma-0"

        with open(mtl_path, "w") as handle:
            json.dump(mtl, handle, indent=2, default=str)
        logger.info(f"Updated MTL.json with RTC fields at {mtl_path}")
        return mtl_path
