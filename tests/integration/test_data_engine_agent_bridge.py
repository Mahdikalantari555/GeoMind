from __future__ import annotations

import json
from pathlib import Path

import rasterio
from fastapi.testclient import TestClient
from geofront_api.services.agent import get_agent_service

from tests.integration._raster_fixture import create_synthetic_raster


def test_synthetic_raster_readable_by_rasterio(tmp_path: Path) -> None:
    """Requirement 6 (Task 7.1): Verify synthetic raster is written and readable by rasterio."""
    tif_path = tmp_path / "synthetic_test.tif"
    bounds = (48.19, 30.95, 48.28, 31.05)
    created = create_synthetic_raster(tif_path, bounds=bounds, width=64, height=64, bands=4)
    assert created.exists()

    with rasterio.open(created) as src:
        assert src.count == 4
        assert src.crs is not None
        assert src.crs.to_string() == "EPSG:4326"
        bbox = src.bounds
        assert bbox.left <= bounds[0]
        assert bbox.bottom <= bounds[1]
        assert bbox.right >= bounds[2]
        assert bbox.top >= bounds[3]


def test_agent_geo_zonal_stats_on_synthetic_raster(gateway: TestClient, tmp_path: Path) -> None:
    """Requirement 6 (Task 7.2): geo_zonal_stats tool runs on synthetic raster + sample AOI."""
    service = get_agent_service()
    assert service.is_initialized
    agent_ws = service.settings.workspace

    # Create synthetic raster covering sample.geojson bounds
    tif_path = agent_ws / "sentinel_synthetic.tif"
    create_synthetic_raster(tif_path, bounds=(48.19, 30.95, 48.28, 31.05), bands=4)

    # AOI from sample/sample.geojson
    sample_path = Path("sample/sample.geojson").resolve()
    assert sample_path.exists()
    fc = json.loads(sample_path.read_text(encoding="utf-8"))
    aoi_coords = fc["features"][0]["geometry"]["coordinates"][0]
    aoi_lons = [c[0] for c in aoi_coords]
    aoi_lats = [c[1] for c in aoi_coords]
    aoi_min_lon, aoi_max_lon = min(aoi_lons), max(aoi_lons)
    aoi_min_lat, aoi_max_lat = min(aoi_lats), max(aoi_lats)

    with rasterio.open(tif_path) as src:
        raster_bounds = src.bounds
        # AOI falls strictly inside the raster extent
        assert raster_bounds.left <= aoi_min_lon
        assert raster_bounds.right >= aoi_max_lon
        assert raster_bounds.bottom <= aoi_min_lat
        assert raster_bounds.top >= aoi_max_lat

    # Invoke tool directly via geoagent registry or through gateway POST /api/v1/agent/run
    out_csv = "zonal_results.csv"
    resp = gateway.post(
        "/api/v1/agent/run",
        json={
            "tool": "geo_zonal_stats",
            "args": {
                "raster_tif": str(tif_path),
                "polygons_geojson": str(sample_path),
                "id_field": "OGC_FID",
                "out_csv": out_csv,
            },
        },
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["status"] == "ok"
    assert result["value"]["row_count"] == 1
    assert len(result["artifacts"]) >= 1

    # Output CSV was generated and has statistics
    artifact_path = Path(result["artifacts"][0]["path"])
    assert artifact_path.exists()
    content = artifact_path.read_text(encoding="utf-8")
    assert "mean" in content
    assert "OGC_FID" in content
