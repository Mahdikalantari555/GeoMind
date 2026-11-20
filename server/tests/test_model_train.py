"""Online training routes (add-studio-training-lab §3): /models/train,
/models/versions, /models/rollback — wired to geolearn with the workspace
facade as CandidateMemoryProvider.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from fastapi.testclient import TestClient

from .conftest import wait_job


def _seed_candidates(client: TestClient) -> list[str]:
    """Create two verified candidate memories with cache embeddings."""
    ids: list[str] = []
    contents = [
        {"asset_id": "a1", "label": 1, "crop_type": "wheat", "region": "khuzestan"},
        {"asset_id": "a2", "label": 0, "crop_type": "wheat", "region": "khuzestan"},
    ]
    for content in contents:
        resp = client.post(
            "/api/v1/feedback/candidates",
            json={"content": json.dumps(content), "memory_type": "correction"},
        )
        assert resp.status_code == 200, resp.text
        cid = resp.json()["id"]
        for state in ("supported", "verified"):
            review = client.post(
                f"/api/v1/feedback/candidates/{cid}/review",
                json={"new_state": state, "reviewer_id": "tester"},
            )
            assert review.status_code == 200, review.text
        ids.append(cid)
    return ids


def _seed_embeddings(ws_path: Path) -> None:
    from geolearn.cache import EmbeddingCache

    cache = EmbeddingCache(ws_path / "geolearn")
    cache.insert("a1", np.ones(8, dtype=np.float32))
    cache.insert("a2", -np.ones(8, dtype=np.float32))


class TestModelTrain:
    def test_train_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/models/train", json={})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_train_without_candidates_reports_noop(
        self, client: TestClient, open_ws: dict
    ) -> None:
        """Empty workspace → job completes but must not look like a silent
        success: the detail explains that nothing was trained (fifth pass)."""
        resp = client.post("/api/v1/models/train", json={})
        assert resp.status_code == 202
        job = wait_job(client, resp.json()["job_id"])
        assert job["status"] == "completed", job
        assert job["result"] == {}
        assert "nothing trained" in (job.get("detail") or "")
        assert client.get("/api/v1/models/versions").json()["versions"] == []

    def test_train_job_completes_and_records_version(
        self, client: TestClient, open_ws: dict
    ) -> None:
        ws_path = Path(str(open_ws["body"]["path"]))
        _seed_candidates(client)
        _seed_embeddings(ws_path)

        resp = client.post("/api/v1/models/train", json={"batch_size": 2})
        assert resp.status_code == 202
        job = wait_job(client, resp.json()["job_id"])
        assert job["status"] == "completed", job
        result = job["result"]
        assert result["wheat__khuzestan"]["samples_trained"] == 2

        versions = client.get("/api/v1/models/versions")
        assert versions.status_code == 200
        rows = versions.json()["versions"]
        assert rows, "expected at least one saved version"
        top = rows[0]
        assert top["key"] == ["wheat", "khuzestan"]
        assert top["version"] >= 1
        assert top["n_samples"] == 2
        assert top["sha256"]

    def test_train_progress_streamed(
        self, client: TestClient, open_ws: dict, monkeypatch: Any
    ) -> None:
        """The training job emits job.progress events with stage/percent."""
        ws_path = Path(str(open_ws["body"]["path"]))
        _seed_candidates(client)
        _seed_embeddings(ws_path)

        from geofront_api.events import get_event_bus

        seen: list[dict[str, Any]] = []
        bus = get_event_bus()
        original_publish = bus.publish

        def spy(event: str, payload: dict[str, Any]) -> None:
            if event in ("job.progress", "job_progress") and payload.get("status") == "running":
                seen.append(payload)
            original_publish(event, payload)

        monkeypatch.setattr(bus, "publish", spy)

        resp = client.post("/api/v1/models/train", json={"batch_size": 2})
        assert resp.status_code == 202
        job = wait_job(client, resp.json()["job_id"])
        assert job["status"] == "completed", job
        running = [p for p in seen if p.get("stage") == "wheat__khuzestan"]
        assert running, "expected stage-tagged progress events"

    def test_rollback_to_prior_version(
        self, client: TestClient, open_ws: dict
    ) -> None:
        ws_path = Path(str(open_ws["body"]["path"]))
        _seed_candidates(client)
        _seed_embeddings(ws_path)

        # first training round → version 1
        job1 = wait_job(client, client.post("/api/v1/models/train", json={"batch_size": 2}).json()["job_id"])
        assert job1["status"] == "completed"
        versions = client.get("/api/v1/models/versions").json()["versions"]
        assert versions

        # rollback to that version
        target = versions[0]["version"]
        resp = client.post(
            "/api/v1/models/rollback",
            json={"key": ["wheat", "khuzestan"], "version": target},
        )
        assert resp.status_code == 200
        assert resp.json()["rolled_back"] is True

    def test_rollback_emits_audit_event(
        self, client: TestClient, open_ws: dict, monkeypatch: Any
    ) -> None:
        """A successful rollback publishes a model_rolled_back audit event."""
        ws_path = Path(str(open_ws["body"]["path"]))
        _seed_candidates(client)
        _seed_embeddings(ws_path)
        job1 = wait_job(
            client, client.post("/api/v1/models/train", json={"batch_size": 2}).json()["job_id"]
        )
        assert job1["status"] == "completed"
        versions = client.get("/api/v1/models/versions").json()["versions"]
        target = versions[0]["version"]

        from geofront_api.events import get_event_bus

        seen: list[dict[str, Any]] = []
        bus = get_event_bus()
        original_publish = bus.publish

        def spy(event: str, payload: dict[str, Any]) -> None:
            if event == "model_rolled_back":
                seen.append(payload)
            original_publish(event, payload)

        monkeypatch.setattr(bus, "publish", spy)
        resp = client.post(
            "/api/v1/models/rollback",
            json={"key": ["wheat", "khuzestan"], "version": target},
        )
        assert resp.status_code == 200
        assert seen, "expected a model_rolled_back audit event"
        assert seen[0]["key"] == ["wheat", "khuzestan"]
        assert seen[0]["version"] == target

    def test_rollback_unknown_version_404(
        self, client: TestClient, open_ws: dict
    ) -> None:
        resp = client.post(
            "/api/v1/models/rollback",
            json={"key": ["wheat", "khuzestan"], "version": 999},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "rollback_failed"

    def test_versions_empty_ok(self, client: TestClient, open_ws: dict) -> None:
        resp = client.get("/api/v1/models/versions")
        assert resp.status_code == 200
        assert resp.json()["versions"] == []
