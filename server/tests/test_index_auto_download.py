"""Tests for index auto-download fallback behaviour."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from geofront_api.main import create_app
from geofront_api.state import AppState


@pytest.fixture
def client():
    app = create_app()
    app.state.geofront_state = AppState()
    return TestClient(app)


class TestIndexAutoDownloadFallback:
    def test_build_without_workspace_returns_409(self, client):
        resp = client.post("/api/v1/index/build")
        assert resp.status_code == 409

    def test_rebuild_without_workspace_returns_409(self, client):
        resp = client.post("/api/v1/index/rebuild")
        assert resp.status_code == 409

    def test_build_calls_auto_download_onnx(self, client, open_ws):
        """With onnx backend, _auto_download_fallback is invoked before build."""
        client.put(
            "/api/v1/workspace/settings",
            json={"embedding_backend": "onnx", "offline": False},
        )

        called = []

        def tracking_fallback(ws):
            called.append(ws.settings.embedding_backend)

        with patch(
            "geofront_api.routers.index._auto_download_fallback",
            tracking_fallback,
        ):
            client.post("/api/v1/index/build")
            assert called == ["onnx"]

    def test_build_skips_auto_download_for_hashing(self, client, open_ws):
        """With hashing backend, _auto_download_fallback returns early."""
        called = []

        def tracking_fallback(ws):
            called.append(ws.settings.embedding_backend)

        with patch(
            "geofront_api.routers.index._auto_download_fallback",
            tracking_fallback,
        ):
            client.post("/api/v1/index/build")
            assert called == ["hashing"]
