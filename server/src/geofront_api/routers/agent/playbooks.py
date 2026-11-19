"""Agent playbooks route: list, get, run, and save playbooks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent/playbooks", tags=["agent"])


_PLAYBOOK_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def _validate_playbook_name(name: str) -> None:
    if not _PLAYBOOK_NAME_RE.fullmatch(name):
        raise GeoFrontError(
            code="invalid_playbook_name", message=f"Invalid playbook name: {name!r}", status_code=422
        )


def _playbook_path(workspace: Path, name: str) -> Path:
    root = workspace / "playbooks"
    target = root / f"{name.replace('-', '_')}.md"
    if not target.resolve().is_relative_to(root.resolve()):
        raise GeoFrontError(
            code="path_outside_sandbox",
            message="Playbook path escapes the playbooks directory",
            status_code=403,
        )
    return target


def _require_initialized(service: Any) -> None:
    if not service.is_initialized:
        raise GeoFrontError(
            code="agent_not_ready",
            message="Agent not initialized. Open a workspace first.",
            status_code=409,
        )


@router.get("")
async def list_playbooks() -> dict[str, object]:
    """List all playbooks with validation status."""
    from geoagent.playbooks import load_playbooks, validate_playbook

    service = get_agent_service()
    _require_initialized(service)

    found = load_playbooks(service.settings.workspace)
    registry = service.registry

    items = []
    for pb in found:
        problems = validate_playbook(pb, registry)
        items.append(
            {
                "name": pb.name,
                "version": pb.version,
                "triggers": pb.triggers,
                "params": pb.params,
                "steps": [{"tool": s.tool, "args": s.args} for s in pb.steps],
                "valid": len(problems) == 0,
                "problems": problems,
                "source_path": pb.source_path,
            }
        )

    return {"playbooks": items}


@router.get("/{name:path}")
async def get_playbook(name: str) -> dict[str, object]:
    """Get a specific playbook by name."""
    _validate_playbook_name(name)
    from geoagent.playbooks import parse_playbook, validate_playbook

    service = get_agent_service()
    _require_initialized(service)

    target = _playbook_path(service.settings.workspace, name)
    if not target.exists():
        raise GeoFrontError(
            code="playbook_not_found",
            message=f"Playbook not found: {name}",
            status_code=404,
        )

    text = target.read_text(encoding="utf-8")
    pb = parse_playbook(text, str(target))
    problems = validate_playbook(pb, service.registry)

    return {
        "name": pb.name,
        "version": pb.version,
        "triggers": pb.triggers,
        "params": pb.params,
        "steps": [{"tool": s.tool, "args": s.args} for s in pb.steps],
        "valid": len(problems) == 0,
        "problems": problems,
        "source_path": str(target),
        "content": text,
    }


class RunPlaybookRequest(BaseModel):
    params: dict[str, Any] = {}


@router.post("/{name}/run")
async def run_playbook(name: str, body: RunPlaybookRequest) -> dict[str, object]:
    """Run a playbook directly (no LLM involved)."""
    from geoagent.registry import RunContext

    service = get_agent_service()
    registry = service.registry

    tool_name = f"pb_{name.replace('-', '_')}"
    tool_def = registry.get(tool_name)
    if tool_def is None:
        raise GeoFrontError(
            code="playbook_not_found",
            message=f"Playbook not found: {name}",
            status_code=404,
        )

    import time

    ctx = RunContext(
        store=service.store,
        workspace_dir=service.settings.workspace,
        sandbox_roots=service.settings.resolve_sandbox_roots(),
        settings=service.settings,
        max_tool_calls=500,
        deadline=time.monotonic() + 880.0,
    )

    result = await run_in_threadpool(registry.call, tool_name, body.params, ctx)
    dump: dict[str, Any] = result.model_dump(mode="json")
    return dump


class SavePlaybookRequest(BaseModel):
    name: str
    content: str


@router.post("/save")
async def save_playbook(req: SavePlaybookRequest) -> dict[str, object]:
    """Save a new playbook."""
    _validate_playbook_name(req.name)
    from geoagent.playbooks import parse_playbook, save_playbook, validate_playbook

    service = get_agent_service()
    _require_initialized(service)

    # Validate the playbook content
    pb = parse_playbook(req.content)
    problems = validate_playbook(pb, service.registry)

    if problems:
        raise GeoFrontError(
            code="invalid_playbook",
            message=f"Playbook validation failed: {'; '.join(problems[:5])}",
            status_code=422,
            detail={"problems": problems},
        )

    _playbook_path(service.settings.workspace, req.name)
    path = save_playbook(service.settings.workspace, req.name, req.content)
    return {"saved": str(path), "name": pb.name}
