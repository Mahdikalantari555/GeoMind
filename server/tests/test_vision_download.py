"""Tests for the vision model download endpoint."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient


def _create_workspace(client: TestClient, tmp_path: Any, offline: bool) -> dict[str, object]:
    path = str(tmp_path / "ws")
    resp = client.post(
        "/api/v1/workspace/create",
        json={"path": path, "name": "M2", "offline": offline},
    )
    assert resp.status_code == 201, resp.text
    return {"path": path}


def _wait_job(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(100):
        body = client.get(f"/api/v1/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def test_vision_download_enqueues_job_and_updates_settings(
    client: TestClient, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _create_workspace(client, tmp_path, offline=False)
    monkeypatch.setattr(
        "geomemory.embeddings.vision_downloader.download_vision_model",
        lambda settings: "/tmp/vision/weights.pth",
    )

    resp = client.post("/api/v1/models/vision/download")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert "job_id" in body
    job_id = body["job_id"]

    job = _wait_job(client, job_id)
    assert job["status"] == "completed", job
    assert job["result"] == "/tmp/vision/weights.pth"

    workspace_resp = client.get("/api/v1/workspace")
    assert workspace_resp.status_code == 200
    assert workspace_resp.json()["settings"]["vision_path"] == "/tmp/vision/weights.pth"


def test_vision_download_offline_guard_returns_503(client: TestClient, tmp_path: Any) -> None:
    _create_workspace(client, tmp_path, offline=True)

    resp = client.post("/api/v1/models/vision/download")
    assert resp.status_code == 503, resp.text
    body = resp.json()
    assert body["error"]["code"] == "vision_unavailable"
    assert body["error"]["detail"]["offline"] is True
