from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory
from geomemory.storage.repositories.entity_repo import EntityRepository

from ..errors import GeoFrontError
from ..state import get_state

router = APIRouter(tags=["entities"])
log = logging.getLogger("geofront.entities")


def _require_ws() -> GeoMemory:
    return get_state().require_workspace()


@router.get("/entities")
async def list_entities(kind: str | None = Query(default=None)) -> dict[str, object]:
    """List workspace entities, optionally filtered by ``kind``."""
    ws = _require_ws()
    repo = await run_in_threadpool(EntityRepository, ws.conn)
    wid = await run_in_threadpool(ws._workspace_id)
    if kind is not None:
        entities = await run_in_threadpool(repo.list_by_kind, kind, workspace_id=wid)
    else:
        entities = await run_in_threadpool(repo.list_by_workspace, wid)
    return {"entities": [e.model_dump(mode="json") for e in entities]}


@router.get("/entities/{entity_id}/relations")
async def get_entity_relations(entity_id: str) -> dict[str, object]:
    """Return relations using ``Workspace.traverse`` internally."""
    ws = _require_ws()
    result = await run_in_threadpool(ws.traverse, entity_id, depth=1)
    if result.get("entity") is None:
        raise GeoFrontError(
            code="entity_not_found",
            message=f"Entity not found: {entity_id}",
            status_code=404,
        )
    relations: list[dict[str, Any]] = []
    for rel in cast(list[dict[str, Any]], result.get("relations") or []):
        relations.append({
            "source_id": rel["source"]["id"],
            "predicate": rel["predicate"],
            "target_id": rel.get("target", {}).get("id"),
            "confidence": float(rel["confidence"]),
            "created_at": rel.get("created_at"),
        })
    return {"relations": relations}
