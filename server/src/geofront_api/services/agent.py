"""Agent service: manages the GeoAgent core lifecycle.

One agent instance per active workspace. The service lazily initializes
the agent when a workspace is open and provides access to the registry,
store, and core.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from geoagent.agent import AgentCore, build_backend
from geoagent.config import AgentSettings, ProviderSettings
from geoagent.registry import Registry
from geoagent.store import Store
from geoagent.tools import advisor_tools, cli_runner, gis_tools, memory_tools

from ..errors import GeoFrontError


class AgentService:
    """Manages the GeoAgent core for the active workspace.

    Lazily initializes the agent on first use. The agent's workspace
    is set to a subdirectory of the GeoMemory workspace.
    """

    def __init__(self) -> None:
        self._core: AgentCore | None = None
        self._registry: Registry | None = None
        self._store: Store | None = None
        self._settings: AgentSettings | None = None
        self._workspace_path: Path | None = None
        self._lock = asyncio.Lock()

    @property
    def workspace_path(self) -> Path | None:
        return self._workspace_path

    @property
    def is_initialized(self) -> bool:
        # Workspace-bound check: ensure core exists and workspace path matches active workspace
        if self._core is None or self._workspace_path is None:
            return False
        # Verify that the stored workspace still matches the directory on disk
        # If the workspace was switched elsewhere, is_initialized will be False until re-init
        return self._workspace_path.exists()

    @property
    def registry(self) -> Registry:
        if self._registry is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._registry

    @property
    def store(self) -> Store:
        if self._store is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._store

    @property
    def settings(self) -> AgentSettings:
        if self._settings is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._settings

    @property
    def core(self) -> AgentCore:
        if self._core is None:
            raise GeoFrontError(
                code="agent_not_ready",
                message="Agent not initialized. Open a workspace first.",
                status_code=409,
            )
        return self._core

    def init(
        self,
        workspace_path: Path,
        workspace_settings: Any = None,
        workspace: Any = None,
    ) -> None:
        """Initialize the agent for the given workspace path with workspace settings."""
        agent_workspace = workspace_path / "geoagent"
        agent_workspace.mkdir(parents=True, exist_ok=True)

        if workspace is None:
            try:
                from ..state import get_state

                st = get_state()
                if st.workspace is not None and st.workspace_path == workspace_path:
                    workspace = st.workspace
            except Exception:
                pass

        if workspace_settings is None:
            if workspace is not None and hasattr(workspace, "settings"):
                workspace_settings = workspace.settings
            else:
                try:
                    from ..state import get_state

                    st = get_state()
                    if st.workspace is not None and hasattr(st.workspace, "settings"):
                        workspace_settings = st.workspace.settings
                except Exception:
                    pass

        if workspace_settings is None:
            settings_yaml = workspace_path / "settings.yaml"
            if settings_yaml.is_file():
                try:
                    from geomemory.core.config import load_settings

                    workspace_settings = load_settings(settings_yaml)
                except Exception:
                    pass

        provider_kwargs: dict[str, Any] = {}
        if workspace_settings is not None:
            if getattr(workspace_settings, "llm_api_base_url", None):
                provider_kwargs["base_url"] = workspace_settings.llm_api_base_url
            if getattr(workspace_settings, "llm_model_id", None):
                provider_kwargs["model"] = workspace_settings.llm_model_id
            if getattr(workspace_settings, "llm_api_key_env", None):
                provider_kwargs["api_key_env"] = workspace_settings.llm_api_key_env
            if getattr(workspace_settings, "llm_temperature", None) is not None:
                provider_kwargs["temperature"] = workspace_settings.llm_temperature
            if getattr(workspace_settings, "llm_timeout_s", None) is not None:
                provider_kwargs["timeout_s"] = workspace_settings.llm_timeout_s

        provider = ProviderSettings(**provider_kwargs) if provider_kwargs else ProviderSettings()

        settings = AgentSettings(
            workspace=agent_workspace,
            memory_workspace=str(workspace_path),
            provider=provider,
        )

        if workspace is not None:
            memory_tools.set_memory(workspace)

        store = Store(agent_workspace / "agent.db")
        registry = self._build_registry(settings, store)
        try:
            backend = build_backend(settings)
        except Exception:  # noqa: BLE001 — LLM key missing → abstention backend
            from geoagent.llm.base import ChatResponse

            class _AbstainBackend:
                def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                    return ChatResponse(
                        content="LLM unavailable — no API key configured. Configure the key on the server and retry."
                    )

            backend = _AbstainBackend()

        core = AgentCore(settings, backend, registry, store)
        self._settings = settings
        self._registry = registry
        self._store = store
        self._core = core
        self._workspace_path = workspace_path

    def _build_registry(self, settings: AgentSettings, store: Store) -> Registry:
        registry = Registry()
        memory_tools.register(registry)
        gis_tools.register(registry)
        advisor_tools.register(registry)
        cli_runner.register_from_config(registry, settings)
        register_parity_tools(registry)
        return registry

    def reset(self) -> None:
        """Reset the agent (e.g., when workspace closes)."""
        if self._store is not None:
            self._store.close()
        self._core = None
        self._registry = None
        self._store = None
        self._settings = None
        self._workspace_path = None


# ── Gateway parity tools (change: add-studio-knowledge-agent §4) ─────────────
#
# `roi_create` and `data_download` give the agent the exact same stores and
# flows the Studio UI uses: ROIs land in the gateway ROI store
# (`<workspace>/rois.json`, served by `POST /rois`) and scene downloads run
# the shared `run_scene_download` flow (same fetch + asset registration as
# `POST /data/download`, minus the background-job wrapper).


def _main_workspace_dir(ctx: Any) -> Path:
    """Resolve the GeoMemory workspace dir from the agent context."""
    settings = ctx.settings
    memory_ws = getattr(settings, "memory_workspace", None)
    if memory_ws:
        return Path(str(memory_ws))
    # Agent workspace is `<ws>/geoagent` — its parent is the main workspace.
    return Path(ctx.workspace_dir).parent


def register_parity_tools(registry: Registry) -> None:
    """Register ``roi_create`` + ``data_download`` on the agent registry."""
    from geoagent.registry import ArtifactRef, ToolDefinition, ToolResult

    @registry.register(
        ToolDefinition(
            name="roi_create",
            description=(
                "Create a named ROI (bbox or polygon, WGS84 lon/lat ring) in "
                "the gateway ROI store — the same store the Studio map uses. "
                "Returns the ROI with server-computed area (ha) and centroid."
            ),
            params={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "ROI display name"},
                    "kind": {
                        "type": "string",
                        "enum": ["bbox", "polygon"],
                        "description": "ROI shape kind",
                    },
                    "coords": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                        "description": "lon/lat ring points (closed automatically)",
                    },
                },
                "required": ["name", "kind", "coords"],
                "additionalProperties": False,
            },
            returns="ROI dict: id, name, kind, coords, geometry, areaHa, centroid, createdAt",
            timeout_s=30.0,
        )
    )
    def roi_create(args: dict[str, Any], ctx: Any) -> ToolResult:
        from ..services.roi_store import create_roi

        coords = args["coords"]
        if len(coords) < 3:
            raise ValueError("coords must contain at least 3 lon/lat points")
        for point in coords:
            if not (-180.0 <= point[0] <= 180.0) or not (-90.0 <= point[1] <= 90.0):
                raise ValueError("coords must be [lon, lat] pairs within WGS84 bounds")
        roi = create_roi(
            _main_workspace_dir(ctx),
            name=args["name"],
            kind=args["kind"],
            coords=coords,
        )
        return ToolResult(status="ok", value=roi)

    @registry.register(
        ToolDefinition(
            name="data_download",
            description=(
                "Download a satellite scene (Landsat/Sentinel) clipped to an "
                "ROI polygon and register every band as a workspace asset — "
                "the same fetch + provenance flow as POST /data/download. "
                "Runs synchronously and returns band files + asset ids."
            ),
            params={
                "type": "object",
                "properties": {
                    "scene_id": {"type": "string", "description": "STAC scene id"},
                    "roi": {
                        "type": "object",
                        "description": "GeoJSON Polygon geometry for the ROI",
                    },
                    "sensor": {"type": "string", "enum": ["landsat", "sentinel"]},
                    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["scene_id", "roi", "sensor", "date_from", "date_to"],
                "additionalProperties": False,
            },
            returns="scene_id, date, cloud_cover, directory, band_files, asset_ids",
            timeout_s=1800.0,
        )
    )
    def data_download(args: dict[str, Any], ctx: Any) -> ToolResult:
        try:
            from ..services.scene_download import run_scene_download
        except ImportError as exc:  # designed unavailability, not a crash
            return ToolResult(
                status="failed",
                error=f"data_download unavailable: data_engine.fetch not installed ({exc})",
            )
        roi = args["roi"]
        if not isinstance(roi, dict) or roi.get("type") != "Polygon" or not roi.get("coordinates"):
            raise ValueError("roi must be a GeoJSON Polygon geometry")
        ws = memory_tools.get_memory()
        if ws is None:
            try:
                from geomemory import GeoMemory

                ws = GeoMemory.open(str(_main_workspace_dir(ctx)))
            except Exception as exc:  # noqa: BLE001 — no workspace → designed failure
                return ToolResult(
                    status="failed",
                    error=f"data_download unavailable: no open workspace ({exc})",
                )
        result = run_scene_download(
            ws,
            scene_id=args["scene_id"],
            roi=roi,
            sensor=args["sensor"],
            date_from=args["date_from"],
            date_to=args["date_to"],
        )
        workspace_dir = _main_workspace_dir(ctx)
        artifacts = [
            ArtifactRef(path=str(workspace_dir / rel))
            for rel in result["band_files"].values()
        ]
        return ToolResult(status="ok", value=result, artifacts=artifacts)


_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


def reset_agent_service() -> None:
    global _agent_service
    if _agent_service is not None:
        _agent_service.reset()
    _agent_service = None
