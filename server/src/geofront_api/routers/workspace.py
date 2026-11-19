from __future__ import annotations

import contextlib
import logging
import os
import re
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from geomemory import (
    GeoMemory,
    GeoMemoryError,
    WorkspaceConfig,
    WorkspaceExistsError,
    WorkspaceNotFoundError,
)

from ..errors import GeoFrontError
from ..events import get_event_bus
from ..schemas import (
    CreateWorkspaceRequest,
    OpenWorkspaceRequest,
    UpdateSettingsRequest,
    WorkspaceSuggestion,
)
from ..services.agent import get_agent_service, reset_agent_service
from ..state import get_default_workspace_root, get_state

router = APIRouter(prefix="/workspace", tags=["workspace"])
log = logging.getLogger("geofront.workspace")
_WORKSPACE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,80}")


# Restrict which process environment names can receive workspace credentials.
_LLM_KEY_ENV_RE = re.compile(r"GEOMEMORY_[A-Z0-9_]+")


def _validate_key_env(name: str) -> str | None:
    normalized = name.strip()
    return normalized if _LLM_KEY_ENV_RE.fullmatch(normalized) else None


def _secrets_path(ws_path: Path | str) -> Path:
    return Path(ws_path) / ".geofront" / "secrets.json"


def _load_persisted_secrets(ws_path: Path | str) -> dict[str, str]:
    p = _secrets_path(ws_path)
    if not p.is_file():
        return {}
    try:
        import json

        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def _save_persisted_secrets(ws_path: Path | str, secrets: dict[str, str]) -> None:
    p = _secrets_path(ws_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    import json

    p.write_text(json.dumps(secrets, indent=2), encoding="utf-8")


def _open_workspace_path(raw_path: str) -> GeoMemory:
    """Open the workspace at ``raw_path``.

    Workspaces are stored nested under ``path/<name>/`` (see create). If the
    given path is not itself a workspace but contains exactly one workspace
    subdirectory, open that — so a user can pass the parent directory.
    """
    ws: GeoMemory | None = None
    try:
        ws = GeoMemory.open(raw_path)
    except WorkspaceNotFoundError:
        parent = Path(raw_path).expanduser()
        if not parent.is_dir():
            raise
        for child in sorted(parent.iterdir()):
            if child.is_dir():
                try:
                    ws = GeoMemory.open(child)
                    break
                except WorkspaceNotFoundError:
                    continue
        if ws is None:
            raise

    if getattr(ws.settings, "persist_secrets", False):
        secrets = _load_persisted_secrets(ws.path)
        for k, v in secrets.items():
            validated = _validate_key_env(k)
            if validated is None:
                log.warning("secrets.json: ignoring non-conforming env var name %r", k)
                continue
            if v:
                os.environ[validated] = v
    return ws


def _require_or_409() -> GeoMemory:
    return get_state().require_workspace()


def _settings_dict(ws: GeoMemory) -> dict[str, object]:
    return cast(dict[str, object], ws.settings.model_dump(mode="json"))


def _settings_response(settings: Any) -> dict[str, object]:
    return cast(dict[str, object], settings.model_dump(mode="json"))


@router.post("/create", status_code=201)
async def create_workspace(req: CreateWorkspaceRequest) -> dict[str, object]:
    state = get_state()
    # Resolve empty path → DEFAULT_WORKSPACE_ROOT (GEOFOND_WORKSPACE)
    raw = (req.path or "").strip()
    if not raw:
        from ..state import get_default_workspace_root

        base = get_default_workspace_root()
    else:
        base = Path(raw).expanduser()
    # Files must live in path/workspacename/ — enforce nested mkdir per spec
    safe_name = req.name.strip()
    if not _WORKSPACE_NAME_RE.fullmatch(safe_name) or ".." in safe_name:
        raise GeoFrontError(
            code="invalid_workspace_name",
            message="Workspace name must start with a letter or digit and contain only letters, digits, spaces, '.', '-', or '_'.",
            status_code=422,
        )
    target = base / safe_name if base.name != safe_name else base
    target.mkdir(parents=True, exist_ok=True)
    full_path = str(target.resolve())
    log.info("create workspace: target=%s name=%s base=%s", full_path, req.name, req.path)
    async with state.write_lock:
        await state._close_locked()
        config = WorkspaceConfig(
            name=req.name,
            language=req.language,  # type: ignore[arg-type]
            offline=req.offline,
            model_path=req.model_path,
            embedding_path=req.embedding_path,
            vision_path=req.vision_path,
            default_collection=req.default_collection,
        )
        try:
            ws = await run_in_threadpool(GeoMemory.create, full_path, config)
        except WorkspaceExistsError as exc:
            raise GeoFrontError(
                code="workspace_exists",
                message=f"Workspace already exists at {full_path}. Use open instead.",
                status_code=409,
            ) from exc
        except GeoMemoryError as exc:
            raise GeoFrontError(
                code="workspace_create_failed", message=str(exc), status_code=400
            ) from exc
        state.workspace = ws
        state.set_active(ws.path)
        # Seed LLM connection from gateway env when not specified by the request —
        # lets a deployed server apply GEOMEMORY_LLM_API_BASE_URL / _MODEL_ID.
        env_overrides = {
            k: os.environ[k]
            for k in ("GEOMEMORY_LLM_API_BASE_URL", "GEOMEMORY_LLM_MODEL_ID")
            if os.environ.get(k)
        }
        if env_overrides:
            mapped = {
                "llm_api_base_url": env_overrides.get("GEOMEMORY_LLM_API_BASE_URL"),
                "llm_model_id": env_overrides.get("GEOMEMORY_LLM_MODEL_ID"),
            }
            try:
                ws.update_settings(**{k: v for k, v in mapped.items() if v is not None})
            except ValueError as exc:
                log.warning("could not apply env LLM defaults: %s", exc)
        get_agent_service().init(ws.path, ws.settings, workspace=ws)
    get_event_bus().publish(
        "workspace_changed", {"status": "open", "path": str(state.workspace_path)}
    )
    return {"status": "open", "path": str(state.workspace_path), "settings": _settings_dict(ws)}


@router.post("/open")
async def open_workspace(req: OpenWorkspaceRequest) -> dict[str, object]:
    log.info("open workspace: path=%s", req.path)
    state = get_state()
    async with state.write_lock:
        await state._close_locked()
        try:
            ws = await run_in_threadpool(_open_workspace_path, req.path)
        except WorkspaceNotFoundError as exc:
            raise GeoFrontError(
                code="workspace_not_found",
                message=f"No workspace found at {req.path}.",
                status_code=404,
            ) from exc
        state.workspace = ws
        state.set_active(ws.path)
        get_agent_service().init(ws.path, ws.settings, workspace=ws)
    get_event_bus().publish(
        "workspace_changed", {"status": "open", "path": str(state.workspace_path)}
    )
    return {"status": "open", "path": str(state.workspace_path), "settings": _settings_dict(ws)}


@router.post("/close")
async def close_workspace() -> dict[str, object]:
    state = get_state()
    await state.close()
    reset_agent_service()
    get_event_bus().publish("workspace_changed", {"status": "closed", "path": None})
    return {"status": "closed"}


@router.get("")
async def get_workspace() -> dict[str, object]:
    state = get_state()
    if not state.is_open:
        return {"status": "closed", "path": None, "settings": None}
    return {
        "status": "open",
        "path": str(state.workspace_path),
        "settings": _settings_dict(state.require_workspace()),
    }


@router.get("/suggestions")
async def workspace_suggestions() -> dict[str, object]:
    """List existing workspaces under the default workspace root.

    A directory counts as a workspace if it contains the ``.geomemory`` marker
    file (or a ``geomemory.db``). The result is sorted by path so the UI can
    present a "recent/existing workspaces" suggestion list.
    """
    root = get_default_workspace_root()
    suggestions: list[WorkspaceSuggestion] = []
    if root.is_dir():
        try:
            children = sorted(root.iterdir())
        except OSError:
            children = []
        for child in children:
            if not child.is_dir():
                continue
            # A workspace may live directly at `child` or nested one level
            # under it (create nests as <path>/<name>/). Check both.
            found: list[Path] = []
            if _is_workspace_dir(child):
                found.append(child)
            else:
                try:
                    for grandchild in sorted(child.iterdir()):
                        if grandchild.is_dir() and _is_workspace_dir(grandchild):
                            found.append(grandchild)
                except OSError:
                    pass
            for ws_path in found:
                suggestions.append(
                    WorkspaceSuggestion(
                        path=str(ws_path.resolve()),
                        name=ws_path.name,
                        created=None,
                    )
                )
    return {"root": str(root.resolve()), "suggestions": suggestions}


def _is_workspace_dir(path: Path) -> bool:
    """Return True if ``path`` looks like a GeoMemory workspace."""
    return (path / ".geomemory").is_file() or (path / "geomemory.db").is_file()


@router.get("/stats")
async def workspace_stats() -> dict[str, object]:
    ws = _require_or_409()
    async with get_state().write_lock:
        return await run_in_threadpool(ws.stats)


@router.put("/settings")
async def update_settings(req: UpdateSettingsRequest) -> dict[str, object]:
    ws = _require_or_409()
    # Handle llm_api_key: set server env var at runtime, never persist to workspace DB
    raw = req.model_dump(exclude_unset=True, exclude_none=False)
    api_key_value = raw.pop("llm_api_key", None)
    explicit_key_env = req.llm_api_key_env
    key_env: str | None = None
    if explicit_key_env is not None or api_key_value is not None:
        effective = (
            explicit_key_env
            or ws.settings.llm_api_key_env
            or "GEOMEMORY_LLM_API_KEY"
        )
        key_env = _validate_key_env(effective.strip() or "GEOMEMORY_LLM_API_KEY")
        if key_env is None:
            raise GeoFrontError(
                code="invalid_key_env",
                message="llm_api_key_env must match GEOMEMORY_[A-Z0-9_]+.",
                status_code=422,
            )
        if explicit_key_env is not None:
            raw["llm_api_key_env"] = key_env
    changes = {k: v for k, v in raw.items() if v is not None}
    async with get_state().write_lock:
        try:
            # If only the key was being set and no other changes, skip ws.update_settings
            if changes:
                updated = await run_in_threadpool(ws.update_settings, **changes)
            else:
                updated = ws.settings
        except ValueError as exc:
            raise GeoFrontError(code="invalid_setting", message=str(exc), status_code=422) from exc

    if api_key_value is not None and key_env is not None:
        os.environ[key_env] = str(api_key_value)
        log.info("LLM API key set via settings for env var %s (value hidden)", key_env)

    # Optional local secret persistence
    should_persist = getattr(updated, "persist_secrets", False)
    if should_persist:
        if api_key_value is not None and key_env is not None:
            cur = _load_persisted_secrets(ws.path)
            cur[key_env] = str(api_key_value)
            _save_persisted_secrets(ws.path, cur)
    elif changes.get("persist_secrets") is False:
        # If explicitly disabled, remove secrets file
        sec_file = _secrets_path(ws.path)
        if sec_file.is_file():
            with contextlib.suppress(OSError):
                sec_file.unlink()
    # If key was set, optionally re-init agent backend so it picks up new key without workspace reload
    if api_key_value is not None or changes.keys() & {"llm_provider", "llm_api_base_url", "llm_model_id", "llm_api_key_env"}:
        try:
            get_agent_service().init(
                get_state().workspace_path,  # type: ignore[arg-type]
                updated,
                workspace=get_state().workspace,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("agent re-init after key set failed: %s", exc)
    return _settings_response(updated)
