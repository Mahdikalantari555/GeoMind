from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import WorkspaceNotOpenError

log = logging.getLogger("geofront.state")


def get_default_workspace_root() -> Path:
    """Resolve the workspace root with dev/container defaults.

    Canonical env: ``GEOMIND_WORKSPACE``. Legacy ``GEOFOND_WORKSPACE`` is
    accepted as a fallback. Default is <project_root>/Workspaces (gitignored);
    the container default is /workspace.
    """
    env = (
        os.environ.get("GEOMIND_WORKSPACE", "").strip()
        or os.environ.get("GEOFOND_WORKSPACE", "").strip()
    )
    if env:
        return Path(env).expanduser()
    # Container image uses /workspace; prefer it when it exists
    if Path("/workspace").exists():
        return Path("/workspace")
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "Workspaces"


DEFAULT_WORKSPACE_ROOT = get_default_workspace_root()


def _active_workspace_state_path() -> Path:
    """Path to the persisted active-workspace marker.

    Lives under the resolved workspace root so it is gitignored alongside
    the workspaces themselves (`.geofront/active_workspace`). Overridable via
    canonical ``GEOMIND_STATE_PATH``; the legacy ``GEOFONT_STATE_PATH``
    spelling (a typo) is still accepted as a fallback for existing tests and
    deployments.
    """
    env = (
        os.environ.get("GEOMIND_STATE_PATH", "").strip()
        or os.environ.get("GEOFONT_STATE_PATH", "").strip()
    )
    if env:
        return Path(env).expanduser()
    return get_default_workspace_root() / ".geofront" / "active_workspace"


def _read_active_workspace_path() -> Path | None:
    """Return the persisted active workspace path, or None if missing/invalid."""
    p = _active_workspace_state_path()
    if not p.is_file():
        return None
    try:
        raw = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    return candidate if candidate.exists() else None


def _write_active_workspace_path(path: Path | None) -> None:
    """Persist (or clear) the active workspace path marker."""
    p = _active_workspace_state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if path is None:
            if p.is_file():
                p.unlink()
        else:
            p.write_text(str(path.resolve()), encoding="utf-8")
    except OSError as exc:
        log.warning("could not persist active workspace marker: %s", exc)


if TYPE_CHECKING:
    from geomemory import GeoMemory


@dataclass
class AppState:
    """Holds the single active workspace and the platform write lock.

    Invariants (AGENTS.md): one uvicorn worker, one active workspace,
    all write operations serialized behind `write_lock`. Blocking facade
    calls must be dispatched to a threadpool, never run on the loop.
    """

    workspace: GeoMemory | None = None
    workspace_path: Path | None = None
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def require_workspace(self) -> GeoMemory:
        if self.workspace is None:
            raise WorkspaceNotOpenError()
        return self.workspace

    @property
    def is_open(self) -> bool:
        return self.workspace is not None

    def set_active(self, path: Path | None) -> None:
        """Update the in-memory active path and persist the marker."""
        self.workspace_path = path
        _write_active_workspace_path(path)

    async def close(self) -> None:
        """Close the active workspace (acquires the write lock)."""
        async with self.write_lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        """Close the active workspace. Caller must hold the write lock."""
        ws = self.workspace
        if ws is None:
            return
        await asyncio.to_thread(ws.close)
        self.workspace = None
        self.set_active(None)

    def llm_health(self) -> dict[str, object]:
        settings = self.workspace.settings if self.workspace is not None else None
        provider = getattr(settings, "llm_provider", None) or "api"
        key_env = getattr(settings, "llm_api_key_env", None) or "GEOMEMORY_LLM_API_KEY"
        base_url = getattr(settings, "llm_api_base_url", None) or os.environ.get(
            "GEOMEMORY_LLM_API_BASE_URL"
        )
        model_id = getattr(settings, "llm_model_id", None) or os.environ.get(
            "GEOMEMORY_LLM_MODEL_ID"
        )
        return {
            "provider": provider,
            "key_env": key_env,
            "key_configured": bool(os.environ.get(key_env, "")),
            "base_url": base_url,
            "model_id": model_id,
        }


_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state


def reset_state() -> None:
    global _state
    _state = AppState()


def restore_active_workspace() -> Path | None:
    """Reopen the persisted active workspace on gateway startup.

    Returns the resolved path if a workspace was reopened, else None. The
    actual open is performed by the caller (lifespan) via the workspace
    router; this helper only resolves and validates the persisted path.
    """
    return _read_active_workspace_path()


def init_state() -> None:
    """Initialize the global AppState singleton (idempotent)."""
    global _state
    if _state is None:
        _state = AppState()
