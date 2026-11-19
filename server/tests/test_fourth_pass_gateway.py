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


def test_directory_paths_are_not_served_as_files(tmp_path, monkeypatch):
    """`download`/`preview` accepted a directory and failed inside FileResponse."""
    from geofront_api.routers.agent import files as files_router

    svc, workspace = _agent_service(tmp_path, monkeypatch)
    (workspace / "runs").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(files_router, "get_agent_service", lambda: svc)
    for call in (files_router.download_file, files_router.preview_file):
        with pytest.raises(GeoFrontError) as exc:
            call(path="runs")
        assert exc.value.code == "not_a_file", call.__name__


def test_map_cannot_read_a_sibling_directory(tmp_path, monkeypatch):
    """The agent workspace's parent was a read root, so sibling dirs were readable."""
    from geofront_api.routers.agent import maps as maps_router

    workspace = tmp_path / "ws"
    workspace.mkdir()
    sibling = tmp_path / "other-project" / "secret.geojson"
    sibling.parent.mkdir()
    sibling.write_text(json.dumps({"type": "FeatureCollection", "features": []}))

    class _State:
        is_open = True
        workspace_path = None

    class _Svc:
        is_initialized = True

        class _S:
            pass

        settings = _S()

    _Svc.settings.workspace = workspace
    monkeypatch.setattr(maps_router, "get_state", lambda: _State())
    monkeypatch.setattr(maps_router, "get_agent_service", lambda: _Svc())
    with pytest.raises(GeoFrontError) as exc:
        asyncio.run(maps_router.get_geojson(path="other-project/secret.geojson"))
    assert exc.value.code == "file_not_found"
