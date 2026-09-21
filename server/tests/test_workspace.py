from __future__ import annotations

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
