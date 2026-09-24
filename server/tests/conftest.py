from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geofront_api.events import reset_event_bus
from geofront_api.jobs import reset_job_manager
from geofront_api.main import create_app
from geofront_api.services.agent import reset_agent_service
from geofront_api.state import reset_state


@pytest.fixture(autouse=True)
def _isolate_geofront_state(tmp_path: Path) -> Iterator[None]:
    state_path = tmp_path / "active_workspace"
    old = os.environ.get("GEOFONT_STATE_PATH")
    os.environ["GEOFONT_STATE_PATH"] = str(state_path)
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("GEOFONT_STATE_PATH", None)
        else:
            os.environ["GEOFONT_STATE_PATH"] = old


@pytest.fixture()
def client() -> TestClient:
    reset_state()
    reset_job_manager()
    reset_event_bus()
    reset_agent_service()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_state()
    reset_job_manager()
    reset_event_bus()
    reset_agent_service()


@pytest.fixture()
def open_ws(client: TestClient, tmp_path: pytest.PathFactory) -> dict[str, object]:
    """Create + open a workspace; return {'path': str}."""
    path = str(tmp_path / "ws")
    resp = client.post("/api/v1/workspace/create", json={"path": path, "name": "M2"})
    assert resp.status_code == 201
    return {"path": path}


def make_collection(client: TestClient, name: str = "docs") -> str:
    resp = client.post("/api/v1/collections", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def wait_job(client: TestClient, job_id: str) -> dict[str, object]:
    import time

    for _ in range(100):
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")
