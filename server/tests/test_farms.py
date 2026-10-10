from __future__ import annotations

import json
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


class TestFarmsRouter:
    def test_list_farms_matches_alias_id_and_returns_farms(
        self, client: TestClient, ws_path: str, tmp_path: Path
    ) -> None:
        client.post("/api/v1/workspace/create", json={"path": ws_path, "name": "FarmWS"})
        actual_ws = Path(client.get("/api/v1/workspace").json()["path"])

        # Place a geojson with "id" property alias in workspace
        farm_geojson = actual_ws / "farms.geojson"
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"id": "farm-alias-99", "crop": "Corn"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[48.1, 31.1], [48.2, 31.1], [48.2, 31.2], [48.1, 31.2], [48.1, 31.1]]],
                    },
                }
            ],
        }
        farm_geojson.write_text(json.dumps(fc))

        resp = client.get("/api/v1/agent/farms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        farm = next(f for f in data["farms"] if f["farm_id"] == "farm-alias-99")
        assert farm["properties"]["crop"] == "Corn"

        # Check detail endpoint
        detail = client.get("/api/v1/agent/farms/farm-alias-99")
        assert detail.status_code == 200
        assert detail.json()["farm"]["farm_id"] == "farm-alias-99"
