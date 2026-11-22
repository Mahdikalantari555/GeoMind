"""Scene acquisition routes (change: add-scene-data-gateway).

POST /data/search    — Planetary Computer STAC search for a drawn ROI
POST /data/download  — 202 job: ROI-clipped band download + asset registration
GET  /data/tiles/{z}/{x}/{y}.png — sandboxed raster tile PNG for MapLibre

The gateway consumes only the ``data_engine.fetch`` public facade; tests
inject fakes by monkeypatching module-level ``stac_search`` (this module)
and ``fetch_scene`` (``services.scene_download``).
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from data_engine.fetch import FetchProgress, SceneSearchError, stac_search
from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from ..errors import GeoFrontError
from ..jobs import get_job_manager
from ..schemas import SceneDownloadRequest, SceneSearchRequest
from ..services import scene_download
from ..state import get_state

router = APIRouter(prefix="/data", tags=["data"])
log = logging.getLogger("geofront.data")

MAX_ZOOM = 22


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


@router.post("/search")
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
    ws = state.require_workspace()
    root = Path(ws.path).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise GeoFrontError(
            code="path_outside_sandbox",
            message=f"Path '{path}' is outside the workspace",
            status_code=403,
        )
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
    stretched: list[np.ndarray[Any, Any]] = []
    for band in data:
        valid = band[np.isfinite(band)]
        if valid.size:
            lo, hi = np.percentile(valid, [2, 98])
        else:
            lo, hi = 0.0, 1.0
        norm = np.clip((band - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
        stretched.append((norm * 255).astype("uint8"))
    arr = np.stack(stretched)

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
