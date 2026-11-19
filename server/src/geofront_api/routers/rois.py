"""ROI routes (change: add-studio-knowledge-agent §4.1).

GET    /rois        — list persisted ROIs (UI + agent share this store)
POST   /rois        — create an ROI (area/centroid computed server-side)
GET    /rois/{id}   — fetch one ROI
DELETE /rois/{id}   — remove one ROI
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from ..errors import GeoFrontError
from ..schemas import RoiCreateRequest
from ..services.roi_store import create_roi, delete_roi, get_roi, load_rois
from ..state import get_state

router = APIRouter(prefix="/rois", tags=["rois"])
log = logging.getLogger("geofront.rois")


def _workspace_dir() -> Path:
    return Path(get_state().require_workspace().path)


def _store_error(exc: ValueError) -> GeoFrontError:
    return GeoFrontError(
        code="roi_store_invalid",
        message=f"ROI store is unreadable: {exc}",
        status_code=422,
    )


@router.get("")
async def list_rois() -> dict[str, Any]:
    """List all ROIs persisted in the active workspace."""
    ws_dir = _workspace_dir()
    try:
        rois = await run_in_threadpool(load_rois, ws_dir)
    except ValueError as exc:
        raise _store_error(exc) from exc
    return {"rois": rois, "count": len(rois)}


@router.post("", status_code=201)
async def create_roi_route(req: RoiCreateRequest) -> dict[str, Any]:
    """Create an ROI; area/centroid are computed server-side."""
    if len(req.coords) < 3:
        raise GeoFrontError(
            code="invalid_request",
            message="coords must contain at least 3 lon/lat points",
            status_code=422,
        )
    for point in req.coords:
        if len(point) != 2 or not (-180.0 <= point[0] <= 180.0) or not (-90.0 <= point[1] <= 90.0):
            raise GeoFrontError(
                code="invalid_request",
                message="coords must be [lon, lat] pairs within WGS84 bounds",
                status_code=422,
            )
    from shapely.geometry import Polygon

    polygon = Polygon(req.coords)
    if not polygon.is_valid or polygon.area == 0:
        raise GeoFrontError(code="invalid_request", message="ROI must enclose a valid nonzero area", status_code=422)
    ws_dir = _workspace_dir()
    async with get_state().write_lock:
        try:
            roi = await run_in_threadpool(
                create_roi, ws_dir, name=req.name, kind=req.kind, coords=req.coords
            )
        except ValueError as exc:
            raise _store_error(exc) from exc
    log.info("roi created: id=%s name=%s", roi["id"], roi["name"])
    return roi


@router.get("/{roi_id}")
async def get_roi_route(roi_id: str) -> dict[str, Any]:
    ws_dir = _workspace_dir()
    try:
        roi = await run_in_threadpool(get_roi, ws_dir, roi_id)
    except ValueError as exc:
        raise _store_error(exc) from exc
    if roi is None:
        raise GeoFrontError(
            code="roi_not_found", message=f"ROI not found: {roi_id}", status_code=404
        )
    return roi


@router.delete("/{roi_id}")
async def delete_roi_route(roi_id: str) -> dict[str, Any]:
    ws_dir = _workspace_dir()
    async with get_state().write_lock:
        try:
            removed = await run_in_threadpool(delete_roi, ws_dir, roi_id)
        except ValueError as exc:
            raise _store_error(exc) from exc
    if not removed:
        raise GeoFrontError(
            code="roi_not_found", message=f"ROI not found: {roi_id}", status_code=404
        )
    return {"deleted": True, "id": roi_id}
