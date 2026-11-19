from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any

import pytest
from fastapi.testclient import TestClient

from geofront_api.services.agent import get_agent_service


def test_blocking_tool_does_not_block_health(
    client: TestClient, open_ws: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()
    release = Event()
    registry = get_agent_service().registry

    class Result:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            return {"status": "ok"}

    def blocked_call(*args: Any) -> Result:
        started.set()
        assert release.wait(5), "test did not release the tool"
        return Result()

    monkeypatch.setattr(registry, "call", blocked_call)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tool = pool.submit(client.post, "/api/v1/agent/tools/geo_search/call", json={})
        try:
            assert started.wait(3)
            health = pool.submit(client.get, "/api/v1/health")
            assert health.result(timeout=2).status_code == 200
            assert not tool.done()
        finally:
            release.set()
        assert tool.result(timeout=3).json() == {"status": "ok"}
