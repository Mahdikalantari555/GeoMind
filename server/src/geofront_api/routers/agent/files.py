"""Agent files route: sandboxed access to workspace artifacts."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, PlainTextResponse

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent/files", tags=["agent"])


@router.get("/list")
def list_files(pattern: str = Query(default="runs/**/*")) -> dict[str, object]:
    """List workspace files matching a glob pattern."""
    service = get_agent_service()
    if not service.is_initialized or service.workspace_path is None:
        raise GeoFrontError(
            code="workspace_not_open", message="No workspace is open.", status_code=409
        )
    workspace = service.workspace_path

    files = []
    for p in sorted(workspace.glob(pattern)):
        if p.is_file():
            files.append(
                {
                    "path": str(p.relative_to(workspace)),
                    "size": p.stat().st_size,
                    "modified": p.stat().st_mtime,
                }
            )

    return {"files": files, "pattern": pattern}


@router.get("/download")
def download_file(path: str = Query()) -> FileResponse:
    """Download a workspace file (sandboxed to workspace roots)."""
    service = get_agent_service()
    if not service.is_initialized or service.workspace_path is None:
        raise GeoFrontError(
            code="workspace_not_open", message="No workspace is open.", status_code=409
        )
    workspace = service.workspace_path

    # Resolve and validate path is within sandbox
    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace):
        raise GeoFrontError(
            code="path_outside_sandbox",
            message=f"Path '{path}' is outside the workspace",
            status_code=403,
        )

    if not target.exists():
        raise GeoFrontError(
            code="file_not_found",
            message=f"File not found: {path}",
            status_code=404,
        )

    return FileResponse(target, filename=target.name)


@router.get("/preview")
def preview_file(path: str = Query()) -> PlainTextResponse:
    """Preview a text file (sandboxed to workspace roots)."""
    service = get_agent_service()
    if not service.is_initialized or service.workspace_path is None:
        raise GeoFrontError(
            code="workspace_not_open", message="No workspace is open.", status_code=409
        )
    workspace = service.workspace_path

    target = (workspace / path).resolve()
    if not target.is_relative_to(workspace):
        raise GeoFrontError(
            code="path_outside_sandbox",
            message=f"Path '{path}' is outside the workspace",
            status_code=403,
        )

    if not target.exists():
        raise GeoFrontError(
            code="file_not_found",
            message=f"File not found: {path}",
            status_code=404,
        )

    content = target.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(content[:50000])
