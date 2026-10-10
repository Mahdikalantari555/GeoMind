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
