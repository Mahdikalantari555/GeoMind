from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from geofront_api.services.agent import get_agent_service

from tests.integration._raster_fixture import create_synthetic_raster


def test_agent_tool_runs_on_workspace(gateway: TestClient) -> None:
    """Requirement 4 (Task 5.1): POST /api/v1/agent/run executes a tool on workspace and returns artifacts."""
    # 1. Ingest a document
    doc_resp = gateway.post(
        "/api/v1/asset",
        json={"filename": "farm_notes.md", "content": "# Farm 0\nIrrigated parcel observations.\n"},
    )
    assert doc_resp.status_code == 201, doc_resp.text

    service = get_agent_service()
    assert service.is_initialized
    agent_ws = service.settings.workspace

    # 2. Prepare synthetic raster and geojson AOI
    tif_path = agent_ws / "canopy.tif"
    create_synthetic_raster(tif_path, bounds=(48.19, 30.95, 48.28, 31.05), bands=4)

    sample_path = Path("sample/sample.geojson").resolve()
    assert sample_path.exists()

    # 3. Call POST /api/v1/agent/run with geo_zonal_stats
    run_resp = gateway.post(
        "/api/v1/agent/run",
        json={
            "tool": "geo_zonal_stats",
            "args": {
                "raster_tif": str(tif_path),
                "polygons_geojson": str(sample_path),
                "id_field": "OGC_FID",
                "out_csv": "zonal_stats_out.csv",
            },
        },
    )
    assert run_resp.status_code == 200, run_resp.text
    result = run_resp.json()

    assert result["status"] == "ok"
    artifacts: list[dict[str, Any]] = result["artifacts"]
    assert len(artifacts) >= 1

    # Verify artifacts reference existing workspace paths
    for artifact in artifacts:
        path = Path(artifact["path"])
        assert path.exists()
        assert str(agent_ws) in str(path.resolve()) or str(service.settings.workspace) in str(
            path.resolve()
        )
