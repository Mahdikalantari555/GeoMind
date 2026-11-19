from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any

import pytest
from fastapi.testclient import TestClient
from geomemory import GeoMemory

from geofront_api.state import get_state
from tests.integration._workspace import make_collection, wait_job


def test_collection_writes_serialize_with_ingest(
    client: TestClient, open_ws: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    collection_id = make_collection(client, "docs")
    state = get_state()
    started = Event()
    release = Event()
    ingest_waiting = Event()
    create = GeoMemory.create_collection
    archive = GeoMemory.archive_collection
    acquire = state.write_lock.acquire

    def blocked_create(ws: GeoMemory, name: str, description: str) -> Any:
        assert state.write_lock.locked()
        started.set()
        assert release.wait(5), "test did not release collection creation"
        return create(ws, name, description)

    def checked_archive(ws: GeoMemory, cid: str) -> bool:
        assert state.write_lock.locked()
        return archive(ws, cid)

    async def observe_waiter() -> bool:
        if state.write_lock.locked():
            ingest_waiting.set()
        return await acquire()

    monkeypatch.setattr(GeoMemory, "create_collection", blocked_create)
    monkeypatch.setattr(GeoMemory, "archive_collection", checked_archive)
    monkeypatch.setattr(state.write_lock, "acquire", observe_waiter)
    with ThreadPoolExecutor(max_workers=1) as pool:
        creation = pool.submit(client.post, "/api/v1/collections", json={"name": "new"})
        try:
            assert started.wait(3)
            response = client.post(
                "/api/v1/ingest/bytes",
                json={"collection_id": collection_id, "filename": "doc.txt", "data_base64": "aGVsbG8="},
            )
            assert response.status_code == 202, response.text
            job_id = response.json()["job_id"]
            assert ingest_waiting.wait(3)
            assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "running"
        finally:
            release.set()
        created = creation.result(timeout=3)
        assert created.status_code == 201, created.text
    assert wait_job(client, job_id)["status"] == "completed"
    assets = client.get("/api/v1/assets", params={"collection_id": collection_id}).json()
    assert len(assets) == 1
    assert client.delete(f"/api/v1/collections/{created.json()['id']}").status_code == 200
