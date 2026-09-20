from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import GeoMemory

from ..errors import GeoFrontError
from ..state import get_state

memory_router = APIRouter(prefix="/memory", tags=["memory"])
research_router = APIRouter(prefix="/research", tags=["memory"])


def _profile_payload(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": profile["name"],
        "kind": profile["kind"],
        "current_beliefs": [cm.model_dump(mode="json") for cm in profile["current_beliefs"]],
        "history": [cm.model_dump(mode="json") for cm in profile["history"]],
        "related_entities": profile["related_entities"],
    }


@memory_router.get("/entities/{entity_name}")
async def get_entity_profile(entity_name: str) -> dict[str, Any]:
    """Entity profile: current beliefs, revision history, related entities."""
    ws: GeoMemory = get_state().require_workspace()

    def _profile() -> dict[str, Any]:
        from geomemory.services.entity_profile_service import EntityProfileService

        return EntityProfileService(ws.conn).get_profile(entity_name)

    profile = await run_in_threadpool(_profile)
    payload = _profile_payload(profile)
    if not payload["current_beliefs"] and not payload["history"] and payload["kind"] is None:
        raise GeoFrontError(
            code="entity_not_found",
            message=f"Entity {entity_name} not found",
            status_code=404,
        )
    return payload


@research_router.get("/timeline")
async def get_research_timeline(
    project: str,
    type: str | None = None,
    as_of: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Project research timeline, ordered by observed_at DESC."""
    ws: GeoMemory = get_state().require_workspace()
    memory_types = [t.strip() for t in type.split(",") if t.strip()] if type else None

    def _timeline() -> dict[str, Any]:
        from geomemory.services.research_timeline_service import ResearchTimelineService

        result = ResearchTimelineService(ws.conn).get_timeline(
            project, memory_types=memory_types, as_of=as_of, offset=offset, limit=limit
        )
        return {
            "project": result["project"],
            "items": [cm.model_dump(mode="json") for cm in result["items"]],
            "total": result["total"],
        }

    return await run_in_threadpool(_timeline)
