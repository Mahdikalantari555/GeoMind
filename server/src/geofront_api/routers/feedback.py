from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from geomemory import FeedbackEvent, GeoMemory, GeoMemoryError
from starlette.background import BackgroundTask

from ..errors import GeoFrontError
from ..schemas import FeedbackRequest
from ..state import get_state

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=201)
async def record_feedback(req: FeedbackRequest) -> dict[str, object]:
    """Record an immutable feedback event (search hit thumbs, answer ratings)."""
    ws: GeoMemory = get_state().require_workspace()
    event = FeedbackEvent(
        target_type=req.target_type,
        target_id=req.target_id,
        label=req.label,
        actor=req.actor,
        payload=req.payload,
        metadata=req.metadata,
    )
    async with get_state().write_lock:
        try:
            stored = await run_in_threadpool(ws.record_feedback, event)
        except GeoMemoryError as exc:
            raise GeoFrontError(code="feedback_failed", message=str(exc)) from exc
    return stored.model_dump(mode="json")


@router.get("/candidates")
async def list_candidates(state: str | None = None) -> list[dict[str, Any]]:
    ws: GeoMemory = get_state().require_workspace()

    def _list() -> list[dict[str, Any]]:
        return [c.model_dump(mode="json") for c in ws.list_candidate_memories(state)]

    return await run_in_threadpool(_list)


@router.post("/candidates")
async def create_candidate(body: dict[str, Any]) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()

    def _create() -> dict[str, Any]:
        cm = ws.create_candidate_memory(
            body.get("content", ""),
            memory_type=body.get("memory_type", "fact"),
            source_feedback_ids=body.get("source_feedback_ids", []),
            author=body.get("author"),
        )
        if body.get("signals"):
            ws.score_candidate_memory(cm.id, body["signals"])
            cm = ws.get_candidate_memory(cm.id) or cm
        return cm.model_dump(mode="json")

    async with get_state().write_lock:
        return await run_in_threadpool(_create)


@router.post("/candidates/{cid}/review")
async def review_candidate(cid: str, body: dict[str, Any]) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    new_state = body.get("new_state") or body.get("state")
    reviewer_id = body.get("reviewer_id")
    note = body.get("note")
    signals = body.get("signals")

    def _review() -> dict[str, Any]:
        if signals:
            ws.score_candidate_memory(cid, signals)
        updated = (
            ws.promote_candidate_memory(cid, new_state, reviewer_id, note)
            if new_state
            else ws.get_candidate_memory(cid)
        )
        if not updated:
            raise GeoFrontError(
                code="not_found", message=f"Candidate {cid} not found", status_code=404
            )
        return updated.model_dump(mode="json")

    async with get_state().write_lock:
        return await run_in_threadpool(_review)


@router.get("/proposals")
async def list_proposals(status: str | None = None) -> list[dict[str, Any]]:
    ws: GeoMemory = get_state().require_workspace()

    def _list() -> list[dict[str, Any]]:
        return [p.model_dump(mode="json") for p in ws.list_proposals(status)]

    return await run_in_threadpool(_list)


@router.post("/proposals/{pid}/approve")
async def approve_proposal(pid: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    reviewer_id = (body or {}).get("reviewer_id")
    note = (body or {}).get("note")

    def _approve() -> dict[str, Any]:
        res = ws.review_proposal(pid, True, reviewer_id, note)
        if not res:
            raise GeoFrontError(
                code="not_found", message=f"Proposal {pid} not found", status_code=404
            )
        return res.model_dump(mode="json")

    async with get_state().write_lock:
        return await run_in_threadpool(_approve)


@router.post("/proposals/{pid}/reject")
async def reject_proposal(pid: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    ws: GeoMemory = get_state().require_workspace()
    reviewer_id = (body or {}).get("reviewer_id")
    note = (body or {}).get("note")

    def _reject() -> dict[str, Any]:
        res = ws.review_proposal(pid, False, reviewer_id, note)
        if not res:
            raise GeoFrontError(
                code="not_found", message=f"Proposal {pid} not found", status_code=404
            )
        return res.model_dump(mode="json")

    async with get_state().write_lock:
        return await run_in_threadpool(_reject)


@router.get("/export")
async def export_feedback(task_type: str) -> FileResponse:
    """Export accepted feedback examples for a task type as a downloadable JSONL."""
    ws = get_state().require_workspace()
    out = Path(tempfile.mkdtemp(prefix="gf-feedback-"))
    try:
        async with get_state().write_lock:
            path = await run_in_threadpool(ws.export_dataset, task_type, out)
    except BaseException as exc:
        shutil.rmtree(out, ignore_errors=True)
        if isinstance(exc, GeoMemoryError):
            raise GeoFrontError(code="feedback_export_failed", message=str(exc)) from exc
        if isinstance(exc, ValueError):
            raise GeoFrontError(
                code="feedback_export_empty",
                message=str(exc),
                status_code=404,
            ) from exc
        raise
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/jsonl",
        background=BackgroundTask(shutil.rmtree, out, ignore_errors=True),
    )
