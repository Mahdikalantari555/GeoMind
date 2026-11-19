"""Counterexamples from the fourth QA pass: gateway sandbox, events, ROI store,
provider discovery and secret-file handling. Synthetic data only.
"""
from __future__ import annotations

import asyncio
import json
import os
import stat

import pytest

from geofront_api.errors import GeoFrontError
from geofront_api.events import get_event_bus, reset_event_bus
from geofront_api.routers import providers
from geofront_api.services import roi_store

# ── sandboxed file listing / artifact download ────────────────────────────────


def _agent_service(tmp_path, monkeypatch):
    from geofront_api.services.agent import AgentService

    workspace = tmp_path / "ws"
    workspace.mkdir()
    svc = AgentService()
    svc.init(workspace)
    return svc, workspace


def test_file_listing_cannot_escape_the_workspace(tmp_path, monkeypatch):
    from geofront_api.routers.agent import files as files_router

    svc, workspace = _agent_service(tmp_path, monkeypatch)
    (tmp_path / "outside-secret.txt").write_text("synthetic-outside")
    monkeypatch.setattr(files_router, "get_agent_service", lambda: svc)
    with pytest.raises(GeoFrontError) as exc:
        files_router.list_files(pattern="../../**/*.txt")
    assert exc.value.code == "path_outside_sandbox"


def test_map_geojson_cannot_read_outside_the_sandbox(tmp_path, monkeypatch):
    from geofront_api.routers.agent import maps as maps_router

    svc, workspace = _agent_service(tmp_path, monkeypatch)
    outside = tmp_path / "outside.geojson"
    outside.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    class _State:
        is_open = True
        workspace_path = workspace

        def require_workspace(self):
            return svc.settings and type("W", (), {"path": str(workspace)})()

    monkeypatch.setattr(maps_router, "get_agent_service", lambda: svc)
    monkeypatch.setattr(maps_router, "get_state", lambda: _State())
    monkeypatch.setattr(maps_router, "_roots", lambda: [svc.settings.workspace])
    with pytest.raises(GeoFrontError) as exc:
        asyncio.run(maps_router.get_geojson(path="../../outside.geojson"))
    assert exc.value.code == "file_not_found"


# ── event bus lifetime ────────────────────────────────────────────────────────


def test_event_bus_reset_binds_to_the_current_loop():
    async def scenario():
        first = get_event_bus()
        first.bind(asyncio.get_running_loop())
        queue = await first.subscribe()
        first.publish("x", {"a": 1})
        await asyncio.sleep(0)
        assert queue.qsize() == 1
        reset_event_bus()
        second = get_event_bus()
        second.bind(asyncio.get_running_loop())
        second.publish("y", {"a": 2})
        await asyncio.sleep(0)
        # The stale subscriber must not receive events from the new bus.
        assert queue.qsize() == 1

    asyncio.run(scenario())


# ── ROI store integrity ──────────────────────────────────────────────────────


def test_corrupt_roi_store_is_reported_instead_of_silently_emptied(tmp_path):
    (tmp_path / roi_store.ROI_FILENAME).write_text("{not json")
    with pytest.raises(ValueError):
        roi_store.load_rois(tmp_path)


def test_roi_listing_failure_is_an_explicit_error(tmp_path, monkeypatch):
    from geofront_api.routers import rois as rois_router

    class _Ws:
        path = str(tmp_path)

    class _State:
        def require_workspace(self):
            return _Ws()

    (tmp_path / roi_store.ROI_FILENAME).write_text("{not json")
    monkeypatch.setattr(rois_router, "get_state", lambda: _State())
    with pytest.raises(Exception) as exc:
        asyncio.run(rois_router.list_rois())
    assert "roi" in str(exc.value).lower()


# ── provider discovery ──────────────────────────────────────────────────────


def test_discovery_without_a_key_does_not_call_the_provider(tmp_path, monkeypatch):
    class _Ws:
        class settings:  # noqa: N801 - attribute name is part of the router contract
            offline = False

    class _State:
        def require_workspace(self):
            return _Ws()

    monkeypatch.setattr(providers, "get_state", lambda: _State())
    monkeypatch.delenv("GEOMEMORY_OPENAI_API_KEY", raising=False)
    called = False

    def _boom(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider must not be contacted without a key")

    monkeypatch.setattr(providers.httpx, "AsyncClient", _boom)
    with pytest.raises(Exception) as exc:
        asyncio.run(providers.discover("OpenAI"))
    assert not called
    assert "key" in str(exc.value).lower()


def test_word_v1_path_is_not_rewritten(tmp_path):
    """A base whose final segment merely contains 'v1' must keep its path."""
    from geoagent.config import AgentSettings, ProviderSettings
    from geoagent.llm import openai_compat

    settings = AgentSettings(
        workspace=tmp_path,
        provider=ProviderSettings(
            base_url="https://example.test/api/v1beta", api_key="synthetic"
        ),
    )
    backend = openai_compat.OpenAICompatBackend(settings)
    assert backend._url == "https://example.test/api/v1beta/chat/completions"


# ── secrets on disk ─────────────────────────────────────────────────────────


def test_persisted_secrets_are_not_world_readable(tmp_path):
    from geofront_api.routers import workspace as ws_router

    ws_router._save_persisted_secrets(tmp_path, {"GEOMEMORY_LLM_API_KEY": "synthetic-key"})
    mode = stat.S_IMODE(os.stat(ws_router._secrets_path(tmp_path)).st_mode)
    assert mode & 0o077 == 0


def test_plaintext_provider_base_is_only_allowed_on_loopback():
    """The key is sent in an Authorization header; http to a remote host leaks it."""
    from geofront_api.routers import providers

    assert providers._valid_base("https://api.example.test/v1", https_only=False) is True
    assert providers._valid_base("http://127.0.0.1:8080/v1", https_only=False) is True
    assert providers._valid_base("http://api.example.test/v1", https_only=False) is False
    assert providers._valid_base("http://10.0.0.5:8000/v1", https_only=False) is False


def test_model_list_url_does_not_double_the_version_segment(monkeypatch):
    from geofront_api.routers import providers

    class _Ws:
        class settings:  # noqa: N801 - router reads `.settings`
            offline = False

    monkeypatch.setattr(
        providers, "get_state", lambda: type("S", (), {"require_workspace": staticmethod(lambda: _Ws())})()
    )

    seen: list[str] = []

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "gpt-x"}]}

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            seen.append(url)
            return _Response()

    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **kw: _Client())
    monkeypatch.setenv("GEOMEMORY_OPENAI_API_KEY", "synthetic")
    asyncio.run(providers.discover("OpenAI"))
    assert seen == ["https://api.openai.com/v1/models"], seen
