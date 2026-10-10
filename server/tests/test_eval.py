from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geofront_api.main import create_app
from geofront_api.state import reset_state


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
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
def ws_path(tmp_path: Path) -> str:
    return str(tmp_path / "ws")


class TestEvalRouter:
    def test_eval_missing_file_returns_404(self, client: TestClient, ws_path: str) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        resp = client.post(
            "/api/v1/eval/run",
            json={"benchmark_path": "/nonexistent/bench.jsonl"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "eval_file_not_found"

    def test_eval_enqueues_background_job_202(self, client: TestClient, ws_path: str, tmp_path: Path) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path})
        bench_file = tmp_path / "bench.jsonl"
        bench_file.write_text('{"question": "test", "relevant_assets": []}\n')

        resp = client.post(
            "/api/v1/eval/run",
            json={"benchmark_path": str(bench_file)},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "job_id" in body
        job_id = body["job_id"]

        # Poll job status
        job_resp = client.get(f"/api/v1/jobs/{job_id}")
        assert job_resp.status_code == 200
        job_data = job_resp.json()
        assert job_data["type"] == "eval_run"
