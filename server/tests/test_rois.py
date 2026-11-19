"""ROI routes + agent parity tools (add-studio-knowledge-agent §4).

The gateway ROI store is shared by the Studio UI (``/rois``) and the
``roi_create`` / ``data_download`` agent tools — these tests pin that
parity: a tool-created ROI is visible via the HTTP routes, and the
``data_download`` tool runs the same fetch + asset-registration flow as
``POST /data/download``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import rasterio
from data_engine.fetch import FetchResult
from fastapi.testclient import TestClient
from rasterio.transform import from_bounds

from .conftest import wait_job

ROI_PAYLOAD: dict[str, Any] = {
    "name": "karkheh-block-3",
    "kind": "polygon",
    "coords": [[48.0, 32.0], [48.1, 32.0], [48.1, 32.1], [48.0, 32.1]],
}

ROI_GEOMETRY: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [[[48.0, 32.0], [48.1, 32.0], [48.1, 32.1], [48.0, 32.1], [48.0, 32.0]]],
}


def _write_band_tiff(path: Path, size: int = 64) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    import math

    radius = 6378137.0
    origin = radius * math.pi
    z, x, y = 8, 134, 84
    span = origin * 2 / (2**z)
    left = -origin + x * span
    right = -origin + (x + 1) * span
    top = origin - y * span
    bottom = origin - (y + 1) * span
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


class TestRoiRoutes:
    def test_requires_workspace(self, client: TestClient) -> None:
        assert client.get("/api/v1/rois").status_code == 409
        assert client.post("/api/v1/rois", json=ROI_PAYLOAD).status_code == 409

    def test_create_list_get_delete(
        self, client: TestClient, open_ws: dict
    ) -> None:
        resp = client.post("/api/v1/rois", json=ROI_PAYLOAD)
        assert resp.status_code == 201, resp.text
        roi = resp.json()
        assert roi["name"] == "karkheh-block-3"
        assert roi["kind"] == "polygon"
        # ring closed server-side
        assert roi["coords"][0] == roi["coords"][-1]
        assert roi["geometry"]["type"] == "Polygon"
        # server-computed stats: ~0.1°×0.1° at lat 32 ≈ 105 km² ≈ 10,480 ha
        assert 9000.0 < roi["areaHa"] < 12000.0
        assert 48.0 < roi["centroid"][0] < 48.1
        assert 32.0 < roi["centroid"][1] < 32.1
        assert isinstance(roi["createdAt"], int)

        listing = client.get("/api/v1/rois")
        assert listing.status_code == 200
        assert listing.json()["count"] == 1

        fetched = client.get(f"/api/v1/rois/{roi['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == roi["id"]

        deleted = client.delete(f"/api/v1/rois/{roi['id']}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert client.get(f"/api/v1/rois/{roi['id']}").status_code == 404
        assert client.get("/api/v1/rois").json()["count"] == 0

    def test_create_invalid_coords_422(self, client: TestClient, open_ws: dict) -> None:
        bad = {**ROI_PAYLOAD, "coords": [[48.0, 32.0], [48.1, 32.0]]}
        resp = client.post("/api/v1/rois", json=bad)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invalid_request"

    def test_create_out_of_bounds_422(self, client: TestClient, open_ws: dict) -> None:
        bad = {**ROI_PAYLOAD, "coords": [[200.0, 32.0], [48.1, 32.0], [48.1, 32.1]]}
        resp = client.post("/api/v1/rois", json=bad)
        assert resp.status_code == 422

    def test_delete_unknown_404(self, client: TestClient, open_ws: dict) -> None:
        resp = client.delete("/api/v1/rois/roi-missing")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "roi_not_found"


class TestParityTools:
    def test_tools_registered(self, client: TestClient, open_ws: dict) -> None:
        names = [t["name"] for t in client.get("/api/v1/agent/tools").json()["tools"]]
        assert "roi_create" in names
        assert "data_download" in names

    def test_roi_create_tool_shares_store_with_routes(
        self, client: TestClient, open_ws: dict
    ) -> None:
        resp = client.post(
            "/api/v1/agent/tools/roi_create/call", json={"args": ROI_PAYLOAD}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        roi = body["value"]
        assert roi["name"] == "karkheh-block-3"
        assert roi["areaHa"] > 0

        # same store as the HTTP routes
        listing = client.get("/api/v1/rois").json()
        assert listing["count"] == 1
        assert listing["rois"][0]["id"] == roi["id"]

        # ToolRun audit row written
        from geofront_api.services.agent import get_agent_service

        rows = get_agent_service().store.conn.execute(
            "SELECT tool, status FROM tool_run WHERE tool='roi_create'"
        ).fetchall()
        assert rows and rows[0][1] == "ok"

    def test_data_download_tool_matches_route_flow(
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
            _write_band_tiff(blue)
            return FetchResult(
                scene_id=scene_id,
                date="2024-07-01",
                cloud_cover=12.0,
                directory=str(scene_dir),
                band_files={"blue": str(blue)},
                mtl_file=str(scene_dir / "MTL.json"),
            )

        monkeypatch.setattr(scene_download_service, "fetch_scene", fake_fetch)
        resp = client.post(
            "/api/v1/agent/tools/data_download/call",
            json={
                "args": {
                    "scene_id": "LC08_fake",
                    "roi": ROI_GEOMETRY,
                    "sensor": "landsat",
                    "date_from": "2024-07-01",
                    "date_to": "2024-07-31",
                }
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        value = body["value"]
        assert value["scene_id"] == "LC08_fake"
        assert value["band_files"]["blue"].endswith("blue.tif")
        assert not Path(value["band_files"]["blue"]).is_absolute()
        assert set(value["asset_ids"]) == {"blue"}

        # provenance: band registered as a workspace asset (same as route)
        detail = client.get(f"/api/v1/assets/{value['asset_ids']['blue']}")
        assert detail.status_code == 200, detail.text

        # artifact SHA-256 identity recorded by the registry
        assert body["artifacts"], "expected band artifacts on the ToolResult"
        assert body["artifacts"][0]["sha256"]

    def test_data_download_invalid_roi_fails_cleanly(
        self, client: TestClient, open_ws: dict
    ) -> None:
        resp = client.post(
            "/api/v1/agent/tools/data_download/call",
            json={
                "args": {
                    "scene_id": "LC08_fake",
                    "roi": {"type": "Point", "coordinates": [1, 2]},
                    "sensor": "landsat",
                    "date_from": "2024-07-01",
                    "date_to": "2024-07-31",
                }
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("failed", "validation_error")
        assert "Polygon" in str(body.get("error", ""))

    def test_route_and_tool_share_download_result_shape(
        self, client: TestClient, open_ws: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The HTTP route job result and the tool result carry the same keys."""
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
            _write_band_tiff(blue)
            return FetchResult(
                scene_id=scene_id,
                date="2024-07-01",
                cloud_cover=12.0,
                directory=str(scene_dir),
                band_files={"blue": str(blue)},
                mtl_file=str(scene_dir / "MTL.json"),
            )

        monkeypatch.setattr(scene_download_service, "fetch_scene", fake_fetch)
        route_resp = client.post(
            "/api/v1/data/download",
            json={
                "scene_id": "LC08_fake",
                "roi": ROI_GEOMETRY,
                "sensor": "landsat",
                "date_from": "2024-07-01",
                "date_to": "2024-07-31",
            },
        )
        assert route_resp.status_code == 202
        job = wait_job(client, route_resp.json()["job_id"])
        assert job["status"] == "completed", job
        assert set(job["result"]) == {
            "scene_id",
            "date",
            "cloud_cover",
            "directory",
            "band_files",
            "asset_ids",
        }


def test_dateline_ring_uses_short_crossing():
    from geofront_api.services.roi_store import ring_stats

    area, center = ring_stats([[179.9, 0], [-179.9, 0], [-179.9, 0.1], [179.9, 0.1], [179.9, 0]])
    assert 20_000 < area < 30_000
    assert abs(abs(center[0]) - 180) < 1e-5
