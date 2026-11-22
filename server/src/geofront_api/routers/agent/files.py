"""Agent files route: sandboxed access to workspace artifacts."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, PlainTextResponse

from ...errors import GeoFrontError
from ...services.agent import get_agent_service

router = APIRouter(prefix="/agent/files", tags=["agent"])


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _safe_glob(pattern: str) -> str:
    """Reject absolute or parent-escaping glob patterns before matching."""
    raw = (pattern or "").strip()
    if not raw:
        raise GeoFrontError(
            code="invalid_request", message="pattern must not be empty", status_code=422
        )
    if Path(raw).is_absolute():
        raise GeoFrontError(
            code="path_outside_sandbox",
            message="pattern must be relative to the workspace",
            status_code=403,
        )
    if any(part == ".." for part in Path(raw).parts):
        raise GeoFrontError(
            code="path_outside_sandbox",
            message="pattern must not contain '..'",
            status_code=403,
        )
    return raw


@router.get("/list")
def list_files(pattern: str = Query(default="runs/**/*")) -> dict[str, object]:
    """List workspace files matching a glob pattern."""
    service = get_agent_service()
    if not service.is_initialized or service.workspace_path is None:
        raise GeoFrontError(
            code="workspace_not_open", message="No workspace is open.", status_code=409
        )
    workspace = service.workspace_path.resolve()

    files = []
    for p in sorted(workspace.glob(_safe_glob(pattern))):
        if not p.is_file():
            continue
        # `Path.glob` accepts `..` segments, so a pattern such as
        # `../../**/*.txt` walks out of the workspace. Reject every match that
        # resolves outside it.
        if not _inside(p, workspace):
            raise GeoFrontError(
                code="path_outside_sandbox",
                message=f"Pattern '{pattern}' escapes the workspace",
                status_code=403,
            )
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

    # Resolve both sides before comparison: a relative workspace path (or a
    # symlink inside it) must not make the containment check permissive.
    workspace = workspace.resolve()
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
    if not target.is_file():
        raise GeoFrontError(
            code="not_a_file", message=f"Not a regular file: {path}", status_code=422
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

    if not target.is_file():
        raise GeoFrontError(
            code="not_a_file", message=f"Not a regular file: {path}", status_code=422
        )
    content = target.read_text(encoding="utf-8", errors="replace")
    return PlainTextResponse(content[:50000])
