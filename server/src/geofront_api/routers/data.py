"""Scene acquisition routes (change: add-scene-data-gateway).

POST /data/search    — Planetary Computer STAC search for a drawn ROI
POST /data/download  — 202 job: ROI-clipped band download + asset registration
GET  /data/tiles/{z}/{x}/{y}.png — sandboxed raster tile PNG for MapLibre

The gateway consumes only the ``data_engine.fetch`` public facade; tests
inject fakes by monkeypatching module-level ``stac_search`` (this module)
and ``fetch_scene`` (``services.scene_download``).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from data_engine.fetch import FetchProgress, SceneSearchError, stac_search
from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import SceneDownloadRequest, SceneSearchRequest, SceneSearchResponse
from ..services import scene_download
from ..state import get_state

router = APIRouter(prefix="/data", tags=["data"])
log = logging.getLogger("geofront.data")

MAX_ZOOM = 22

# Operator-configured basemap/glyph upstreams. The browser never contacts a
# third party: it requests these gateway routes, which fetch from the source
# named here. Point the env vars at a local tile server for air-gapped use
# (see docs/adr/000X-sovereign-map-sources.md). The built-in HTTPS defaults are
# a convenience for connected deployments, not a requirement (S-016).
_BASEMAP_UPSTREAMS = {
    "satellite": (
        "GEOMIND_BASEMAP_SATELLITE_URL",
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ),
    "topo": (
        "GEOMIND_BASEMAP_TOPO_URL",
        "https://tile.opentopomap.org/{z}/{x}/{y}.png",
    ),
    "gray": (
        "GEOMIND_BASEMAP_GRAY_URL",
        "https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
    ),
}
_GLYPHS_UPSTREAM = (
    "GEOMIND_GLYPHS_URL",
    "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
)


def _upstream_template(provider: str) -> str | None:
    entry = _BASEMAP_UPSTREAMS.get(provider)
    return (os.getenv(entry[0], "").strip() or entry[1]) if entry else None


def _safe_upstream(url: str) -> bool:
    """HTTPS (or explicit loopback) only, no embedded credentials/query."""
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError:
        return False
    host = parsed.hostname or ""
    if parsed.scheme == "https":
        return not parsed.username and not parsed.query
    if parsed.scheme == "http":
        return host in {"127.0.0.1", "localhost", "::1"} and not parsed.username and not parsed.query
    return False


async def _proxy_bytes(url: str, media_type: str, max_bytes: int = 6_000_000) -> Response:
    if not _safe_upstream(url):
        raise GeoFrontError(
            code="unapproved_map_source",
            message="Map upstream must be HTTPS (or loopback) with no credentials",
            status_code=422,
        )
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            upstream = await client.get(url)
    except httpx.HTTPError:
        raise GeoFrontError(code="map_source_unavailable", message="Map source unavailable", status_code=404) from None
    if upstream.status_code != 200:
        raise GeoFrontError(code="map_source_unavailable", message="Map source unavailable", status_code=404)
    content = upstream.content[:max_bytes]
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/maps/tiles/{provider}/{z}/{x}/{y}.png")
async def basemap_tile(provider: str, z: int, x: int, y: int) -> Response:
    """Proxy a basemap tile from the operator-configured upstream."""
    template = _upstream_template(provider)
    if template is None:
        raise GeoFrontError(code="unknown_basemap", message=f"Unknown basemap '{provider}'", status_code=404)
    dim = 1 << z
    if not (0 <= z <= MAX_ZOOM and 0 <= x < dim and 0 <= y < dim):
        raise GeoFrontError(code="invalid_tile", message="tile coordinates out of range", status_code=404)
    url = template.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))
    return await _proxy_bytes(url, "image/png")


@router.get("/maps/glyphs/{fontstack}/{range}.pbf")
async def map_glyphs(fontstack: str, range: str) -> Response:
    """Proxy MapLibre glyph ranges from the operator-configured upstream."""
    # Font stacks commonly contain spaces ("Noto Sans Regular").
    if not re.fullmatch(r"[A-Za-z0-9._ -]+", fontstack) or not re.fullmatch(r"[0-9]+-[0-9]+", range):
        raise GeoFrontError(code="invalid_glyph", message="invalid glyph path", status_code=422)
    template = os.getenv(_GLYPHS_UPSTREAM[0], "").strip() or _GLYPHS_UPSTREAM[1]
    url = template.replace("{fontstack}", fontstack).replace("{range}", range)
    return await _proxy_bytes(url, "application/x-protobuf")


def _require_roi_polygon(roi: dict[str, Any]) -> None:
    from shapely.geometry import Polygon

    try:
        rings = roi["coordinates"]
        if roi.get("type") != "Polygon" or not isinstance(rings, list) or not rings:
            raise ValueError
        for ring in rings:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError
            if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in ring):
                raise ValueError
        polygon = Polygon(rings[0], holes=rings[1:])
        if polygon.is_empty or not polygon.is_valid or polygon.area == 0:
            raise ValueError
    except (ValueError, TypeError, IndexError, KeyError):
        raise GeoFrontError(code="invalid_request", message="Expected a valid WGS84 GeoJSON Polygon geometry", status_code=422) from None


@router.post("/search", response_model=SceneSearchResponse)
async def search_scenes(req: SceneSearchRequest) -> dict[str, Any]:
    """Search the catalog for scenes covering the ROI (metadata only)."""
    state = get_state()
    state.require_workspace()
    roi = req.roi.model_dump(mode="json")
    _require_roi_polygon(roi)

    def _run() -> list[dict[str, Any]]:
        refs = stac_search(
            roi,
            sensor=req.sensor,
            date_from=req.date_from,
            date_to=req.date_to,
            max_cloud=req.max_cloud,
        )
        return [asdict(ref) for ref in refs]

    try:
        scenes = await run_in_threadpool(_run)
    except SceneSearchError as exc:
        raise GeoFrontError(
            code="upstream_unavailable", message=str(exc), status_code=502
        ) from exc
    return {"scenes": scenes, "count": len(scenes)}


@router.post("/download", status_code=202)
async def download_scene(req: SceneDownloadRequest) -> dict[str, Any]:
    """Enqueue a scene download job → 202 with live job.progress events."""
    state = get_state()
    ws = state.require_workspace()
    roi = req.roi.model_dump(mode="json")
    _require_roi_polygon(roi)

    def _download(job_id: str) -> Any:
        def _progress(p: FetchProgress) -> None:
            get_job_manager().update_progress(
                job_id, stage=p.stage, percent=p.percent, detail=p.detail
            )

        return scene_download.fetch_scene(
            req.scene_id, roi, sensor=req.sensor,
            date_from=req.date_from, date_to=req.date_to,
            dest=Path(ws.path) / "data" / "scenes", progress_cb=_progress,
        )

    async def _run(job_id: str) -> dict[str, Any]:
        result = await run_in_threadpool(_download, job_id)
        async with state.write_lock:
            return await run_in_threadpool(scene_download.register_scene_download, ws, result)

    record = await get_job_manager().submit("scene_download", _run)
    log.info("scene download enqueued: scene=%s sensor=%s job=%s", req.scene_id, req.sensor, record.id)
    return {"job_id": record.id, "scene_id": req.scene_id}


def _sandbox_path(path: str) -> Path:
    """Resolve a workspace-relative path, rejecting traversal / absolute paths."""
    root = Path(get_state().require_workspace().path).resolve()
    candidate = Path(path)
    if candidate.is_absolute():
        raise GeoFrontError(
            code="path_outside_sandbox",
            message=f"Path '{path}' is outside the workspace",
            status_code=403,
        )
    target = (root / candidate).resolve()
    if not target.is_relative_to(root):
        raise GeoFrontError(
            code="path_outside_sandbox",
            message=f"Path '{path}' is outside the workspace",
            status_code=403,
        )
    return target


_APPROVED_PREVIEW_HOSTS_DEFAULT = {"planetarycomputer.microsoft.com"}


def _preview_host_allowed(host: str) -> bool:
    """Only HTTPS preview hosts on the operator allow-list may be proxied."""
    host = host.lower().rstrip(".")
    extra = {h.strip().lower() for h in os.getenv("GEOMIND_PREVIEW_HOSTS", "").split(",") if h.strip()}
    approved = _APPROVED_PREVIEW_HOSTS_DEFAULT | extra
    if host in approved:
        return True
    # Planetary Computer renders previews from Azure blob storage.
    return host.endswith(".blob.core.windows.net")


@router.get("/scenes/{scene_id}/preview")
async def scene_preview(scene_id: str, url: str = Query(description="STAC preview href")) -> Response:
    """Proxy an approved STAC quicklook. No credentials, no redirects to unapproved hosts."""
    del scene_id  # part of the route contract; the href carries the identity
    try:
        parsed = urlsplit(url)
        _ = parsed.port
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or not _preview_host_allowed(host)
        ):
            raise ValueError("unapproved preview host")
        try:
            if ipaddress.ip_address(host).is_private:
                raise ValueError("private host")
        except ValueError:
            pass  # a hostname, not a literal IP — allowed via the host list
    except ValueError as exc:
        raise GeoFrontError(
            code="unapproved_preview_host",
            message=f"Refusing to proxy preview at an unapproved destination: {exc}",
            status_code=422,
        ) from None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            upstream = await client.get(url)
    except httpx.HTTPError:
        raise GeoFrontError(code="preview_unavailable", message="Preview upstream unavailable", status_code=404) from None
    if upstream.status_code != 200 or not (upstream.content[:4].startswith(b"\x89PNG") or upstream.content[:3] == b"\xff\xd8\xff"):
        raise GeoFrontError(code="preview_unavailable", message="Preview not available", status_code=404)
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "image/png").split(";")[0],
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/tiles/composite/{z}/{x}/{y}.png")
async def get_composite_tile(
    z: int,
    x: int,
    y: int,
    paths: str = Query(description="Comma-separated workspace-relative band file paths"),
    src_bands: str = Query(default="1", alias="bands", description="Comma-separated 1-based band indexes, one per path"),
) -> Response:
    """Stack 1–4 single-band rasters into an RGB(A) PNG tile (2/98 stretch)."""
    if not (0 <= z <= MAX_ZOOM):
        raise GeoFrontError(code="file_not_found", message="tile zoom out of range", status_code=404)
    dim = 1 << z
    if not (0 <= x < dim and 0 <= y < dim):
        raise GeoFrontError(code="file_not_found", message="tile coordinates out of range", status_code=404)

    source_paths = [part.strip() for part in paths.split(",") if part.strip()]
    try:
        indexes = [int(part) for part in src_bands.split(",")]
    except ValueError as exc:
        raise GeoFrontError(code="invalid_request", message=f"invalid bands '{src_bands}'", status_code=422) from exc
    if not source_paths or len(source_paths) != len(indexes) or not 1 <= len(source_paths) <= 4:
        raise GeoFrontError(
            code="invalid_request",
            message="paths and bands must be comma-separated lists of equal length (1-4 entries)",
            status_code=422,
        )
    if any(not 1 <= i <= 16 for i in indexes):
        raise GeoFrontError(code="invalid_request", message="band indexes must be in [1, 16]", status_code=422)

    targets = [_sandbox_path(p) for p in source_paths]
    for target, rel in zip(targets, source_paths, strict=True):
        if not target.is_file():
            raise GeoFrontError(code="file_not_found", message=f"File not found: {rel}", status_code=404)

    signatures = tuple((str(t), t.stat().st_mtime_ns, t.stat().st_size) for t in targets)
    png = await run_in_threadpool(_cached_composite, signatures, x, y, z, tuple(indexes))
    return Response(content=png, media_type="image/png")


@router.get("/tiles/{z}/{x}/{y}.png")
async def get_tile(
    z: int,
    x: int,
    y: int,
    path: str = Query(description="Workspace-relative raster file path"),
    bands: str = Query(default="1", description="Comma-separated 1-based band indexes"),
) -> Response:
    """Render a Web-Mercator tile from a workspace raster as PNG."""
    state = get_state()
    state.require_workspace()
    target = _sandbox_path(path)
    if not target.is_file():
        raise GeoFrontError(code="file_not_found", message=f"File not found: {path}", status_code=404)
    if not (0 <= z <= MAX_ZOOM):
        raise GeoFrontError(code="file_not_found", message="tile zoom out of range", status_code=404)
    dim = 1 << z
    if not (0 <= x < dim and 0 <= y < dim):
        raise GeoFrontError(code="file_not_found", message="tile coordinates out of range", status_code=404)

    try:
        indexes = [int(part) for part in bands.split(",")]
    except ValueError as exc:
        raise GeoFrontError(
            code="invalid_request", message=f"invalid bands '{bands}'", status_code=422
        ) from exc
    if not indexes or any(not 1 <= i <= 16 for i in indexes) or len(indexes) > 4:
        raise GeoFrontError(
            code="invalid_request",
            message="bands must be 1-4 comma-separated indexes in [1, 16]",
            status_code=422,
        )

    stat = target.stat()
    # Cache by source identity so an edited/overwritten raster is never served
    # from a stale entry.
    png = await run_in_threadpool(
        _cached_tile,
        str(target),
        stat.st_mtime_ns,
        stat.st_size,
        x,
        y,
        z,
        tuple(indexes),
    )
    return Response(content=png, media_type="image/png")


def _render_tile(target: Path, x: int, y: int, z: int, indexes: list[int]) -> bytes:
    """Windowed tile read + 2-98 percentile stretch + PNG encode."""
    import numpy as np
    from rio_tiler.errors import TileOutsideBounds
    from rio_tiler.io import Reader

    try:
        with Reader(str(target)) as reader:
            image = reader.tile(x, y, z, indexes=indexes)
    except TileOutsideBounds as exc:
        raise GeoFrontError(
            code="file_not_found", message="tile outside raster bounds", status_code=404
        ) from exc
    except Exception as exc:  # noqa: BLE001 — unreadable raster
        raise GeoFrontError(
            code="not_a_raster", message=f"cannot read raster tile: {exc}", status_code=422
        ) from exc

    data = np.asarray(image.data, dtype="float64")
    return _png_from_array(np.stack([_stretch_band(band) for band in data]))


def _stretch_band(band: Any) -> Any:
    """2/98 percentile stretch to uint8, ignoring non-finite values."""
    import numpy as np

    valid = band[np.isfinite(band)]
    if valid.size:
        lo, hi = np.percentile(valid, [2, 98])
    else:
        lo, hi = 0.0, 1.0
    norm = np.clip((band - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return (norm * 255).astype("uint8")


def _png_from_array(arr: Any) -> bytes:
    from rasterio.io import MemoryFile

    profile: dict[str, Any] = {
        "driver": "PNG",
        "width": arr.shape[2],
        "height": arr.shape[1],
        "count": arr.shape[0],
        "dtype": "uint8",
    }
    with MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(arr)
        return bytes(memfile.read())


def _render_composite(
    targets: list[Path], x: int, y: int, z: int, indexes: list[int]
) -> bytes:
    """Read one tile from each source and stack the stretched channels."""
    import numpy as np
    from rio_tiler.errors import TileOutsideBounds
    from rio_tiler.io import Reader

    channels: list[Any] = []
    for target, band_index in zip(targets, indexes, strict=True):
        try:
            with Reader(str(target)) as reader:
                image = reader.tile(x, y, z, indexes=band_index)
        except TileOutsideBounds as exc:
            raise GeoFrontError(
                code="file_not_found", message="tile outside raster bounds", status_code=404
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise GeoFrontError(
                code="not_a_raster", message=f"cannot read raster tile: {exc}", status_code=422
            ) from exc
        data = np.asarray(image.data, dtype="float64")
        channels.append(_stretch_band(data[0]))
    return _png_from_array(np.stack(channels))


@lru_cache(maxsize=256)
def _cached_composite(
    signatures: tuple[tuple[str, int, int], ...],
    x: int,
    y: int,
    z: int,
    indexes: tuple[int, ...],
) -> bytes:
    # signatures (path + mtime + size) are part of the cache key; mtime/size
    # invalidate stale entries when a band file is replaced.
    return _render_composite([Path(s[0]) for s in signatures], x, y, z, list(indexes))


@lru_cache(maxsize=256)
def _cached_tile(
    path: str,
    mtime_ns: int,
    size: int,
    x: int,
    y: int,
    z: int,
    bands: tuple[int, ...],
) -> bytes:
    """Cache a rendered PNG; mtime/size invalidate it when the raster changes."""
    del mtime_ns, size  # part of the cache key only
    return _render_tile(Path(path), x, y, z, list(bands))
