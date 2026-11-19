"""Scene-acquisition routes: search, download job, tile serving.

All catalog interaction is faked via monkeypatched module-level
``stac_search`` / ``fetch_scene`` (data_engine.fetch facade) — no network.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from data_engine.fetch import (
    FetchResult,
    SceneFetchError,
    SceneRef,
    SceneSearchError,
)
from fastapi.testclient import TestClient
from rasterio.transform import from_bounds

from .conftest import wait_job

ROI: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [[[48.0, 31.0], [48.5, 31.0], [48.5, 31.5], [48.0, 31.5], [48.0, 31.0]]],
}

SEARCH_PAYLOAD = {
    "roi": ROI,
    "sensor": "landsat",
    "date_from": "2024-07-01",
    "date_to": "2024-07-31",
    "max_cloud": 60.0,
}

DOWNLOAD_PAYLOAD = {
    "scene_id": "LC08_fake",
    "roi": ROI,
    "sensor": "landsat",
    "date_from": "2024-07-01",
    "date_to": "2024-07-31",
}


def _scene_ref() -> SceneRef:
    return SceneRef(
        scene_id="LC08_fake",
        datetime="2024-07-01T08:00:00Z",
        cloud_cover=12.0,
        platform="landsat-8",
        bbox=[48.0, 31.0, 48.5, 31.5],
        geometry=ROI,
    )


def _tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    radius = 6378137.0
    origin = radius * math.pi
    span = origin * 2 / (2**z)
    left = -origin + x * span
    right = -origin + (x + 1) * span
    top = origin - y * span
    bottom = origin - (y + 1) * span
    return left, bottom, right, top


def _write_band_tiff(path: Path, size: int = 64) -> None:
    """Create a small single-band GeoTIFF aligned to a Web-Mercator tile."""
    path.parent.mkdir(parents=True, exist_ok=True)
    z, x, y = 8, 134, 84
    left, bottom, right, top = _tile_bounds(z, x, y)
    transform = from_bounds(left, bottom, right, top, size, size)
    data = np.linspace(1, size * size, size * size, dtype="uint16").reshape(size, size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=size,
        width=size,
        count=1,
        dtype="uint16",
        crs="EPSG:3857",
        transform=transform,
    ) as dst:
        dst.write(data, 1)


class TestSceneSearch:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/data/search", json=SEARCH_PAYLOAD)
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "workspace_not_open"

    def test_invalid_roi_422(self, client: TestClient, open_ws: dict) -> None:
        bad = {**SEARCH_PAYLOAD, "roi": {"type": "Point", "coordinates": [1, 2]}}
        resp = client.post("/api/v1/data/search", json=bad)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invalid_request"

    def test_invalid_sensor_422(self, client: TestClient, open_ws: dict) -> None:
        bad = {**SEARCH_PAYLOAD, "sensor": "modis"}
        resp = client.post("/api/v1/data/search", json=bad)
        assert resp.status_code == 422

    def test_invalid_dates_422(self, client: TestClient, open_ws: dict) -> None:
        bad = {**SEARCH_PAYLOAD, "date_from": "07/01/2024"}
        resp = client.post("/api/v1/data/search", json=bad)
        assert resp.status_code == 422

    def test_search_returns_scenes(
        self, client: TestClient, open_ws: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from geofront_api.routers import data as data_router

        captured: dict[str, Any] = {}

        def fake_search(roi: Any, **kwargs: Any) -> list[SceneRef]:
            captured.update(kwargs)
            return [_scene_ref()]

        monkeypatch.setattr(data_router, "stac_search", fake_search)
        resp = client.post("/api/v1/data/search", json=SEARCH_PAYLOAD)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        scene = body["scenes"][0]
        assert scene["scene_id"] == "LC08_fake"
        assert scene["bbox"] == [48.0, 31.0, 48.5, 31.5]
        assert captured["sensor"] == "landsat"
        assert captured["max_cloud"] == 60.0

    def test_search_upstream_error_502(
        self, client: TestClient, open_ws: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from geofront_api.routers import data as data_router

        def fake_search(roi: Any, **kwargs: Any) -> list[SceneRef]:
            raise SceneSearchError("planetary computer down")

        monkeypatch.setattr(data_router, "stac_search", fake_search)
        resp = client.post("/api/v1/data/search", json=SEARCH_PAYLOAD)
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "upstream_unavailable"


class TestSceneDownload:
    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.post("/api/v1/data/download", json=DOWNLOAD_PAYLOAD)
        assert resp.status_code == 409

    def test_download_job_lifecycle(
        self, client: TestClient, open_ws: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from geofront_api.services import scene_download as scene_download_service

        def fake_fetch(
            scene_id: str,
            roi: Any,
            *,
            sensor: str,
            date_from: str,
            date_to: str,
            dest: Path,
            progress_cb: Any = None,
            fetcher: Any = None,
        ) -> FetchResult:
            scene_dir = Path(dest) / "landsat_20240701_047_030"
            blue = scene_dir / "blue.tif"
            green = scene_dir / "green.tif"
            _write_band_tiff(blue)
            _write_band_tiff(green)
            if progress_cb is not None:
                progress_cb(
                    type("P", (), {"scene_id": scene_id, "stage": "downloading", "percent": 50, "detail": None})()
                )
            return FetchResult(
                scene_id=scene_id,
                date="2024-07-01",
                cloud_cover=12.0,
                directory=str(scene_dir),
                band_files={"blue": str(blue), "green": str(green)},
                mtl_file=str(scene_dir / "MTL.json"),
            )

        monkeypatch.setattr(scene_download_service, "fetch_scene", fake_fetch)
        resp = client.post("/api/v1/data/download", json=DOWNLOAD_PAYLOAD)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        job = wait_job(client, job_id)
        assert job["status"] == "completed", job
        result = job["result"]
        assert result["scene_id"] == "LC08_fake"
        assert result["band_files"]["blue"].endswith("blue.tif")
        assert not Path(result["band_files"]["blue"]).is_absolute()
        assert set(result["asset_ids"]) == {"blue", "green"}

        # provenance: bands registered as workspace assets
        for asset_id in result["asset_ids"].values():
            detail = client.get(f"/api/v1/assets/{asset_id}")
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body.get("id", (body.get("asset") or {}).get("id")) == asset_id

        # progress events were streamed through the SSE bus
        progress_seen = client.get("/api/v1/jobs/" + job_id).json()
        assert progress_seen["percent"] == 100

    def test_download_failure_marks_job_error(
        self, client: TestClient, open_ws: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from geofront_api.services import scene_download as scene_download_service

        def fake_fetch(scene_id: str, roi: Any, **kwargs: Any) -> FetchResult:
            raise SceneFetchError("scene vanished from catalog")

        monkeypatch.setattr(scene_download_service, "fetch_scene", fake_fetch)
        resp = client.post("/api/v1/data/download", json=DOWNLOAD_PAYLOAD)
        assert resp.status_code == 202
        job = wait_job(client, resp.json()["job_id"])
        assert job["status"] == "error"
        assert "vanished" in str(job.get("error", ""))


class TestTiles:
    @pytest.fixture()
    def band_file(self, open_ws: dict) -> str:
        # open_ws["path"] is the parent dir; the real workspace root is in body.path
        ws_path = Path(str(open_ws["body"]["path"]))
        rel = "data/scenes/testscene/blue.tif"
        _write_band_tiff(ws_path / rel)
        return rel

    def test_requires_workspace(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/data/tiles/8/134/84.png", params={"path": "x.tif"}
        )
        assert resp.status_code == 409

    def test_sandbox_escape_403(self, client: TestClient, open_ws: dict) -> None:
        resp = client.get(
            "/api/v1/data/tiles/8/134/84.png", params={"path": "../outside.tif"}
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "path_outside_sandbox"

    def test_missing_file_404(self, client: TestClient, open_ws: dict) -> None:
        resp = client.get(
            "/api/v1/data/tiles/8/134/84.png", params={"path": "nope.tif"}
        )
        assert resp.status_code == 404

    def test_renders_png_tile(
        self, client: TestClient, open_ws: dict, band_file: str
    ) -> None:
        resp = client.get(
            "/api/v1/data/tiles/8/134/84.png", params={"path": band_file}
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        # PNG magic bytes
        assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(resp.content) > 100

    def test_out_of_bounds_tile_404(
        self, client: TestClient, open_ws: dict, band_file: str
    ) -> None:
        resp = client.get(
            "/api/v1/data/tiles/3/0/0.png", params={"path": band_file}
        )
        assert resp.status_code == 404

    def test_invalid_zoom_404(
        self, client: TestClient, open_ws: dict, band_file: str
    ) -> None:
        resp = client.get(
            "/api/v1/data/tiles/99/0/0.png", params={"path": band_file}
        )
        assert resp.status_code == 404

    def test_invalid_bands_422(
        self, client: TestClient, open_ws: dict, band_file: str
    ) -> None:
        resp = client.get(
            "/api/v1/data/tiles/8/134/84.png",
            params={"path": band_file, "bands": "abc"},
        )
        assert resp.status_code == 422


class TestJobManagerJobId:
    def test_submit_passes_job_id_to_callable(self) -> None:
        import asyncio

        from geofront_api.jobs import JobManager, reset_job_manager

        async def scenario() -> None:
            reset_job_manager()
            mgr = JobManager()

            seen: list[str] = []

            def with_id(job_id: str) -> dict[str, Any]:
                seen.append(job_id)
                return {"got": job_id}

            record = await mgr.submit("probe", with_id)
            await mgr.wait_for(record.id)
            assert seen == [record.id]

            def without_id() -> str:
                return "ok"

            record2 = await mgr.submit("probe2", without_id)
            await mgr.wait_for(record2.id)
            assert record2.result == "ok"
            await mgr.aclose()
            reset_job_manager()

        asyncio.run(scenario())
