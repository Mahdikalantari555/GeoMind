"""Regression tests for gateway auth, secret routing and disclosure (S-006…S-011)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _auth_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tests run with auth off; each test opts in explicitly."""
    monkeypatch.setenv("GEOMIND_AUTH", "off")
    monkeypatch.delenv("GEOMIND_API_TOKEN", raising=False)
    monkeypatch.delenv("GEOMIND_ADMIN_TOKEN", raising=False)


def _enable_auth(monkeypatch: pytest.MonkeyPatch, token: str = "api-token") -> None:
    monkeypatch.setenv("GEOMIND_AUTH", "on")
    monkeypatch.setenv("GEOMIND_API_TOKEN", token)


def test_api_requires_bearer_token(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_auth(monkeypatch)
    missing = client.get("/api/v1/workspace")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"
    assert missing.headers.get("WWW-Authenticate") == "Bearer"

    wrong = client.get("/api/v1/workspace", headers={"Authorization": "Bearer wrong"})
    assert wrong.status_code == 401

    ok = client.get("/api/v1/workspace", headers={"Authorization": "Bearer api-token"})
    assert ok.status_code == 200


def test_health_stays_public(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_auth(monkeypatch)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_admin_scope_on_privileged_routes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_auth(monkeypatch)
    monkeypatch.setenv("GEOMIND_ADMIN_TOKEN", "admin-token")
    user = {"Authorization": "Bearer api-token"}
    admin = {"Authorization": "Bearer admin-token"}

    for path in ("/api/v1/providers", "/api/v1/environment/overrides"):
        assert client.get(path, headers=user).status_code == 403, path
        assert client.get(path, headers=admin).status_code == 200, path

    # PUT settings requires admin; 409 (no workspace) is fine, 403 is not.
    resp = client.put("/api/v1/workspace/settings", json={}, headers=user)
    assert resp.status_code == 403
    resp = client.put("/api/v1/workspace/settings", json={}, headers=admin)
    assert resp.status_code in (200, 409)


def test_health_does_not_leak_paths_or_env_names(client: TestClient, open_ws: Any) -> None:
    body = client.get("/health").json()
    assert body["workspace"]["path"] is None
    assert set(body["llm"]) == {"provider", "key_configured"}


def test_422_never_echoes_submitted_secrets(
    client: TestClient, open_ws: Any
) -> None:
    resp = client.put(
        "/api/v1/workspace/settings",
        json={"llm_api_key": "supersecret-key", "batch_size": 0},
    )
    assert resp.status_code == 422
    assert "supersecret-key" not in resp.text
    for error in resp.json()["error"]["detail"]:
        assert "input" not in error
        assert "ctx" not in error


def test_secret_settings_routed_to_env_not_persisted_or_returned(
    client: TestClient, open_ws: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GEOMEMORY_QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("GEOMEMORY_CLOUDFLARE_API_TOKEN", raising=False)

    resp = client.put(
        "/api/v1/workspace/settings",
        json={
            "qdrant_api_key": "qdrant-secret-value",
            "cloudflare_api_token": "cloudflare-secret-value",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["secrets_configured"]["qdrant_key_configured"] is True
    assert body["secrets_configured"]["cloudflare_token_configured"] is True
    assert "qdrant-secret-value" not in resp.text
    assert "cloudflare-secret-value" not in resp.text
    assert "qdrant_api_key" not in body
    assert "cloudflare_api_token" not in body
    assert __import__("os").environ["GEOMEMORY_QDRANT_API_KEY"] == "qdrant-secret-value"
    assert (
        __import__("os").environ["GEOMEMORY_CLOUDFLARE_API_TOKEN"]
        == "cloudflare-secret-value"
    )

    ws_path = Path(str(open_ws["path"]))
    for file in ws_path.rglob("*"):
        if file.is_file():
            text = file.read_text(encoding="utf-8", errors="ignore")
            assert "qdrant-secret-value" not in text, file
            assert "cloudflare-secret-value" not in text, file


def test_job_sse_stream_has_no_result_or_raw_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from geofront_api import events as events_mod
    from geofront_api.jobs import JobManager

    async def scenario() -> None:
        bus = events_mod.EventBus()
        bus.bind(asyncio.get_running_loop())
        monkeypatch.setattr(events_mod, "get_event_bus", lambda: bus)
        queue = await bus.subscribe()

        async def boom() -> None:
            raise RuntimeError("leaked-url https://user:pass@example.invalid")

        manager = JobManager()
        record = await manager.submit("failing", boom)
        await manager.wait_for(record.id, timeout=2.0)

        payloads: list[dict[str, Any]] = []
        while not queue.empty():
            payloads.append(queue.get_nowait())

        assert payloads
        assert record.public()["error"] == "job_failed"
        assert record.public()["error_id"]
        assert "leaked-url" not in str(payloads)
        assert "leaked-url" not in str(record.public())
        for payload in payloads:
            assert "result" not in payload["data"]
            assert payload["data"].get("error") in (None, "job_failed")

    asyncio.run(scenario())
