"""Scene search and download facade over the Planetary Computer fetchers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from data_engine.fetch.types import (
    FetchProgress,
    FetchProgressCallback,
    FetchResult,
    SceneFetcher,
    SceneFetchError,
    SceneIntegrityError,
    SceneRef,
    SceneSearchError,
    emit_progress,
    scenes_from_rows,
)
from data_engine.io.errors import PartialDataError as IoPartialDataError

logger = logging.getLogger(__name__)

SENSORS = ("landsat", "sentinel", "sentinel-1", "sentinel-1-rtc")


def _build_fetcher(sensor: str, *, max_cloud: float = 70.0) -> SceneFetcher:
    """Instantiate the io fetcher for a sensor (lazy — heavy imports)."""
    normalized = sensor.strip().lower()
    if normalized == "landsat":
        from data_engine.io.planetary_computer_fetcher import (
            PlanetaryComputerLandsatFetcher,
        )

        return PlanetaryComputerLandsatFetcher(max_cloud_cover=max_cloud)
    if normalized == "sentinel":
        from data_engine.io.planetary_computer_fetcher import (
            SentinelPlanetaryComputerFetcher,
        )

        return SentinelPlanetaryComputerFetcher(max_cloud_cover=max_cloud)
    if normalized in ("sentinel-1", "sentinel1"):
        from data_engine.io.planetary_computer_fetcher import (
            Sentinel1PlanetaryComputerFetcher,
        )

        return Sentinel1PlanetaryComputerFetcher(max_cloud_cover=max_cloud)
    if normalized in ("sentinel-1-rtc", "sentinel1-rtc"):
        from data_engine.io.planetary_computer_fetcher import (
            Sentinel1RtcPlanetaryComputerFetcher,
        )

        return Sentinel1RtcPlanetaryComputerFetcher(max_cloud_cover=max_cloud)
    raise SceneSearchError(
        f"unknown sensor '{sensor}'; expected one of {', '.join(SENSORS)}"
    )


def stac_search(
    roi_geometry: dict[str, Any] | Any,
    *,
    sensor: str = "landsat",
    date_from: str,
    date_to: str,
    max_cloud: float = 70.0,
    fetcher: SceneFetcher | None = None,
    progress_cb: FetchProgressCallback | None = None,
) -> list[SceneRef]:
    """Search the catalog for scenes covering the ROI (metadata only).

    ``fetcher`` injects a provider; production callers omit it and get the
    Planetary Computer fetcher for the requested sensor.
    """
    provider = fetcher or _build_fetcher(sensor, max_cloud=max_cloud)
    emit_progress(progress_cb, FetchProgress(scene_id="*", stage="search", percent=0))
    try:
        rows = provider.search_scenes(roi_geometry, (date_from, date_to))
    except SceneFetchError:
        raise
    except Exception as exc:  # noqa: BLE001 — mapped into the facade's errors
        raise SceneSearchError(f"STAC search failed: {exc}") from exc
    refs = scenes_from_rows(rows)
    emit_progress(
        progress_cb,
        FetchProgress(
            scene_id="*", stage="search", percent=100, detail=f"{len(refs)} scenes"
        ),
    )
    return refs


def fetch_scene(
    scene_id: str,
    roi_geometry: dict[str, Any] | Any,
    *,
    sensor: str = "landsat",
    date_from: str,
    date_to: str,
    dest: str | Path,
    progress_cb: FetchProgressCallback | None = None,
    fetcher: SceneFetcher | None = None,
) -> FetchResult:
    """Download one scene (ROI-clipped bands) into ``dest/<scene dir>/``.

    Resumable at fetcher level: re-requesting a downloaded scene
    short-circuits instead of re-downloading.
    """
    provider = fetcher or _build_fetcher(sensor)
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    emit_progress(
        progress_cb,
        FetchProgress(scene_id=scene_id, stage="fetch", percent=10, detail="fetching bands"),
    )
    try:
        results = provider.fetch_scenes(
            roi_geometry,
            (date_from, date_to),
            str(dest_path),
            selected_ids=[scene_id],
        )
    except SceneFetchError:
        raise
    except IoPartialDataError as exc:
        # Keep the io-layer integrity signal distinct from a generic failure.
        raise SceneIntegrityError(
            f"scene '{scene_id}' is incomplete; missing bands: {exc.missing_bands}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — mapped into the facade's errors
        raise SceneFetchError(f"scene download failed: {exc}") from exc

    if not results:
        raise SceneFetchError(f"scene '{scene_id}' did not produce results for the given ROI")
    row = results[0]
    band_files = {k: str(v) for k, v in (row.get("band_files") or {}).items()}
    if not band_files:
        raise SceneIntegrityError(f"scene '{scene_id}' produced no band files")

    # Default RGB mapping, overridable by the fetcher result. SAR scenes have
    # polarisations instead of optical bands; map vv/vh when those are present.
    if "vv" in band_files and "vh" in band_files:
        default_band_map = {"R": "vv", "G": "vh", "B": "vv"}
    else:
        default_band_map = {
            channel: name
            for channel, name in {"R": "red", "G": "green", "B": "blue"}.items()
            if name in band_files
        }
    band_map = {str(k): str(v) for k, v in (row.get("band_map") or default_band_map).items()}

    raw_cloud = row.get("cloud_cover", 0.0)
    result = FetchResult(
        scene_id=str(row.get("scene_id", scene_id)),
        date=str(row.get("date", "")),
        cloud_cover=float(raw_cloud) if raw_cloud is not None else None,
        directory=str(row.get("directory", dest_path)),
        band_files=band_files,
        mtl_file=str(row["mtl_file"]) if row.get("mtl_file") else None,
        band_map=band_map,
        cloud_available=bool(row.get("cloud_available", raw_cloud is not None)),
    )
    emit_progress(
        progress_cb,
        FetchProgress(
            scene_id=scene_id,
            stage="verify",
            percent=90,
            detail=", ".join(sorted(band_files)),
        ),
    )
    emit_progress(
        progress_cb,
        FetchProgress(scene_id=scene_id, stage="done", percent=100, detail=result.directory),
    )
    logger.info("scene fetched: %s (%d bands)", result.scene_id, len(result.band_files))
    return result
