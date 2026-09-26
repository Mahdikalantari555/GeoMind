from __future__ import annotations

import time
from typing import Any, cast

from fastapi.testclient import TestClient


def create_workspace(
    client: TestClient,
    path: str,
    name: str = "M2",
    **settings: Any,
) -> dict[str, object]:
    """Create and open a workspace through the gateway."""
    payload: dict[str, Any] = {"path": path, "name": name, **settings}
    resp = client.post("/api/v1/workspace/create", json=payload)
    assert resp.status_code == 201, f"Failed to create workspace: {resp.text}"
    return {"path": path, "body": resp.json()}


def make_collection(client: TestClient, name: str = "docs") -> str:
    """Create a collection in the active workspace and return its ID."""
    resp = client.post("/api/v1/collections", json={"name": name})
    assert resp.status_code == 201, f"Failed to create collection: {resp.text}"
    return str(resp.json()["id"])


def wait_job(client: TestClient, job_id: str, timeout_s: float = 10.0) -> dict[str, Any]:
    """Poll a background job until completion or failure."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed", "error"):
            return cast(dict[str, Any], body)
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout_s}s")
