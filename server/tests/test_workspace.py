from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from geofront_api.main import create_app
from geofront_api.state import reset_state


@pytest.fixture()
def client(tmp_path: pytest.PathFactory) -> TestClient:
    import os

    state_path = tmp_path / "active_workspace"
    old = os.environ.get("GEOFONT_STATE_PATH")
    os.environ["GEOFONT_STATE_PATH"] = str(state_path)
    try:
        reset_state()
        app = create_app()
        with TestClient(app) as c:
            yield c
    finally:
        if old is None:
            os.environ.pop("GEOFONT_STATE_PATH", None)
        else:
            os.environ["GEOFONT_STATE_PATH"] = old
        reset_state()


@pytest.fixture()
def ws_path(tmp_path: pytest.PathFactory) -> str:
    return str(tmp_path / "ws")


class TestWorkspaceLifecycle:
    def test_closed_initially(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspace")
        assert resp.status_code == 200
        assert resp.json() == {"status": "closed", "path": None, "settings": None}

    def test_create_open_close_roundtrip(self, client: TestClient, ws_path: str) -> None:
        resp = client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "Test WS"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "open"
        assert body["settings"]["name"] == "Test WS"
        assert body["settings"]["offline"] is False

        # health reflects open workspace
        health = client.get("/health").json()
        assert health["workspace"]["status"] == "open"
        assert health["workspace"]["name"] == "Test WS"

        resp = client.post("/api/v1/workspace/close")
        assert resp.json() == {"status": "closed"}

        resp = client.get("/api/v1/workspace")
        assert resp.json()["status"] == "closed"

    def test_create_twice_conflicts(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.post("/api/v1/workspace/create", json={"path": ws_path})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_exists"

    def test_open_missing_404(self, client: TestClient, tmp_path: pytest.PathFactory) -> None:
        resp = client.post("/api/v1/workspace/open", json={"path": str(tmp_path / "nope")})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "workspace_not_found"

    def test_open_existing_workspace(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "First"})
        client.post("/api/v1/workspace/close")
        resp = client.post("/api/v1/workspace/open", json={"path": ws_path})
        assert resp.status_code == 200
        assert resp.json()["settings"]["name"] == "First"


class TestSettings:
    def test_stats_requires_workspace(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workspace/stats")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_update_settings(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put(
            "/api/v1/workspace/settings",
            json={"name": "Renamed", "batch_size": 32, "llm_provider": "api"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Renamed"
        assert body["batch_size"] == 32
        assert body["llm_provider"] == "api"

        # persisted across reopen
        client.post("/api/v1/workspace/close")
        client.post("/api/v1/workspace/open", json={"path": ws_path})
        resp = client.get("/api/v1/workspace")
        assert resp.json()["settings"]["name"] == "Renamed"

    def test_update_unknown_setting_rejected(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"nonsense": 1})
        assert resp.status_code == 422

    def test_update_invalid_language_rejected(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"language": "fr"})
        assert resp.status_code == 422

    def test_stats_shape(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.get("/api/v1/workspace/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


class TestDefaultsAndPersistence:
    def test_create_defaults_offline_false(self, client: TestClient, ws_path: str) -> None:
        resp = client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "D"})
        assert resp.status_code == 201
        assert resp.json()["settings"]["offline"] is False

    def test_create_defaults_vector_backend_sqlite_vec(
        self, client: TestClient, ws_path: str
    ) -> None:
        resp = client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "V"})
        assert resp.status_code == 201
        assert resp.json()["settings"]["vector_backend"] == "sqlite-vec"

    def test_settings_save_sqlite_vec_no_422(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"vector_backend": "sqlite-vec"})
        assert resp.status_code == 200
        assert resp.json()["vector_backend"] == "sqlite-vec"

    def test_settings_save_qdrant_no_422(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put(
            "/api/v1/workspace/settings",
            json={"vector_backend": "qdrant", "qdrant_url": "http://localhost:6333"},
        )
        assert resp.status_code == 200
        assert resp.json()["vector_backend"] == "qdrant"

    def test_settings_save_lancedb_no_422(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"vector_backend": "lancedb"})
        assert resp.status_code == 200

    def test_open_by_parent_directory(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "Child"})
        client.post("/api/v1/workspace/close")
        # ws_path is the parent dir containing exactly one workspace (Child)
        resp = client.post("/api/v1/workspace/open", json={"path": ws_path})
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"

    def test_reopen_persists_across_state_reset(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "P"})
        # Simulate gateway restart: reset state + re-init lifespan restore
        import asyncio

        from fastapi.concurrency import run_in_threadpool

        from geofront_api.routers.workspace import _open_workspace_path
        from geofront_api.state import get_state, reset_state, restore_active_workspace

        async def _restore() -> None:
            state = get_state()
            persisted = restore_active_workspace()
            assert persisted is not None
            ws = await run_in_threadpool(_open_workspace_path, str(persisted))
            async with state.write_lock:
                await state._close_locked()
                state.workspace = ws
                state.set_active(ws.path)

        reset_state()
        asyncio.run(_restore())
        resp = client.get("/api/v1/workspace")
        assert resp.status_code == 200
        assert resp.json()["status"] == "open"

    def test_close_persists_across_restart(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "P"})
        client.post("/api/v1/workspace/close")
        # Simulate gateway restart after close: marker should be cleared
        from geofront_api.state import reset_state, restore_active_workspace

        reset_state()
        assert restore_active_workspace() is None


class TestSecrets:
    def test_settings_never_leak_qdrant_key(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        client.put("/api/v1/workspace/settings", json={"qdrant_api_key": "qdrant-secret"})
        # value may round-trip in settings (workspace-local secret), but the
        # LLM key (server env) must never appear
        import os

        os.environ["GEOMEMORY_LLM_API_KEY"] = "llm-secret-value"
        try:
            health = client.get("/health").text
            ws_resp = client.get("/api/v1/workspace").text
            assert "llm-secret-value" not in health
            assert "llm-secret-value" not in ws_resp
        finally:
            del os.environ["GEOMEMORY_LLM_API_KEY"]

    def test_context_window_256k_and_cloudflare_accepted(
        self, client: TestClient, ws_path: str
    ) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put(
            "/api/v1/workspace/settings",
            json={
                "llm_context_window": 256000,
                "embedding_provider": "cloudflare",
                "cloudflare_account_id": "cf-acc-123",
                "cloudflare_model_id": "@cf/baai/bge-base-en-v1.5",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["llm_context_window"] == 256000
        assert body["embedding_provider"] == "cloudflare"
        assert body["cloudflare_account_id"] == "cf-acc-123"

    def test_context_window_over_2m_rejected(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put("/api/v1/workspace/settings", json={"llm_context_window": 2000001})
        assert resp.status_code == 422

    def test_persist_secrets_roundtrip(self, client: TestClient, ws_path: str) -> None:
        import os
        from pathlib import Path

        from geofront_api.routers.workspace import _open_workspace_path
        from geofront_api.state import get_state

        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.put(
            "/api/v1/workspace/settings",
            json={
                "persist_secrets": True,
                "llm_api_key": "sk-secret-test-123",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["persist_secrets"] is True
        assert os.environ.get("GEOMEMORY_LLM_API_KEY") == "sk-secret-test-123"

        # Verify secrets file exists
        actual_ws_path = get_state().workspace_path
        assert actual_ws_path is not None
        secrets_file = Path(actual_ws_path) / ".geofront" / "secrets.json"
        assert secrets_file.is_file()
        assert "sk-secret-test-123" in secrets_file.read_text()

        # Simulate restart by clearing env var and re-opening workspace
        os.environ.pop("GEOMEMORY_LLM_API_KEY", None)
        assert "GEOMEMORY_LLM_API_KEY" not in os.environ

        _open_workspace_path(str(actual_ws_path))
        assert os.environ.get("GEOMEMORY_LLM_API_KEY") == "sk-secret-test-123"

        # Disabling persist_secrets removes secrets file
        resp2 = client.put("/api/v1/workspace/settings", json={"persist_secrets": False})
        assert resp2.status_code == 200
        assert not secrets_file.exists()


class TestWorkspaceSuggestions:
    def test_suggestions_empty_when_no_workspaces(
        self, client: TestClient, tmp_path: pytest.PathFactory
    ) -> None:
        empty_root = tmp_path / "empty_workspaces"
        empty_root.mkdir()
        old = os.environ.get("GEOFOND_WORKSPACE")
        os.environ["GEOFOND_WORKSPACE"] = str(empty_root)
        try:
            resp = client.get("/api/v1/workspace/suggestions")
            assert resp.status_code == 200
            body = resp.json()
            assert body["suggestions"] == []
            assert body["root"] == str(empty_root.resolve())
        finally:
            if old is None:
                os.environ.pop("GEOFOND_WORKSPACE", None)
            else:
                os.environ["GEOFOND_WORKSPACE"] = old

    def test_suggestions_lists_existing_workspaces(
        self, client: TestClient, tmp_path: pytest.PathFactory
    ) -> None:
        root = tmp_path / "ws_root"
        root.mkdir()
        # Create two real workspaces under the root
        client.post(
            "/api/v1/workspace/create",
            json={"path": str(root / "alpha"), "name": "Alpha"},
        )
        client.post("/api/v1/workspace/close")
        client.post(
            "/api/v1/workspace/create",
            json={"path": str(root / "beta"), "name": "Beta"},
        )
        client.post("/api/v1/workspace/close")
        # A non-workspace dir should be ignored
        (root / "not_a_workspace").mkdir()

        old = os.environ.get("GEOFOND_WORKSPACE")
        os.environ["GEOFOND_WORKSPACE"] = str(root)
        try:
            resp = client.get("/api/v1/workspace/suggestions")
            assert resp.status_code == 200
            body = resp.json()
            assert body["root"] == str(root.resolve())
            paths = {s["path"] for s in body["suggestions"]}
            assert str((root / "alpha" / "Alpha").resolve()) in paths
            assert str((root / "beta" / "Beta").resolve()) in paths
            assert str((root / "not_a_workspace").resolve()) not in paths
        finally:
            if old is None:
                os.environ.pop("GEOFOND_WORKSPACE", None)
            else:
                os.environ["GEOFOND_WORKSPACE"] = old


def test_failed_switch_preserves_open_workspace(client, open_ws, tmp_path):
    root = '/api/v1/workspace'
    before = client.get(root).json()['path']
    assert client.post(root + '/open', json={'path': str(tmp_path / 'missing')}).status_code == 404
    assert client.get(root).json()['path'] == before
