import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from geomemory import GeoMemory

from geofront_api.state import get_state
from tests.integration._workspace import create_workspace, wait_job


def test_vision_download_persists_path_on_gateway_loop(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_workspace(client, str(tmp_path / "ws"), offline=False)
    path = str(tmp_path / "model.onnx")
    monkeypatch.setattr(GeoMemory, "download_vision_model", lambda self: path)

    assert client.portal is not None

    async def gateway_loop() -> asyncio.AbstractEventLoop:
        return asyncio.get_running_loop()

    loop = client.portal.call(gateway_loop)
    lock = get_state().write_lock
    acquire = lock.acquire

    async def check_loop() -> bool:
        # asyncio.Lock only enforces loop affinity under contention; assert
        # it directly so the regression is detected even on an idle server.
        assert asyncio.get_running_loop() is loop
        return await acquire()

    monkeypatch.setattr(lock, "acquire", check_loop)
    response = client.post("/api/v1/models/vision/download")
    assert response.status_code == 202, response.text

    job = wait_job(client, response.json()["job_id"])
    assert job["status"] == "completed", job
    assert job["result"] == path
    assert client.get("/api/v1/workspace").json()["settings"]["vision_path"] == path
