"""Advisor tools tests: farm report orchestration + recommendation evidence."""

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

pytest.importorskip("rasterio")

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import advisor_tools, gis_tools


def make_scene(path: Path, nir_mean: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(abs(hash(str(nir_mean))) % 2**16)
    red = rng.uniform(800, 1200, (16, 16))
    nir = rng.uniform(max(0.0, nir_mean - 300), nir_mean + 300, (16, 16))
    with rasterio.open(
        str(path), "w", driver="GTiff", height=16, width=16, count=4,
        dtype="float32", crs="EPSG:4326",
        transform=from_origin(48.3, 31.6, 0.01, 0.01), nodata=-9999.0,
    ) as dst:
        dst.write(np.zeros((16, 16), dtype="float32"), 1)
        dst.write(np.zeros((16, 16), dtype="float32"), 2)
        dst.write(red.astype("float32"), 3)
        dst.write(nir.astype("float32"), 4)


def make_farms(path: Path) -> None:
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {"farm_id": "farm-12", "crop": "sugarcane"},
             "geometry": {"type": "Polygon", "coordinates": [
                 [[48.30, 31.59], [48.38, 31.59], [48.38, 31.51], [48.30, 31.51], [48.30, 31.59]]]}},
            {"type": "Feature",
             "properties": {"farm_id": "farm-13", "crop": "sugarcane"},
             "geometry": {"type": "Polygon", "coordinates": [
                 [[48.40, 31.59], [48.45, 31.59], [48.45, 31.55], [48.40, 31.55], [48.40, 31.59]]]}},
        ],
    }
    path.write_text(json.dumps(fc), encoding="utf-8")


@pytest.fixture()
def env(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws")
    ws = settings.workspace
    ws.mkdir(parents=True)
    store = Store(ws / "agent.db")
    registry = Registry()
    gis_tools.register(registry)
    advisor_tools.register(registry)
    ctx = RunContext(store=store, workspace_dir=ws,
                     sandbox_roots=[ws], settings=settings)

    make_farms(ws / "farms.geojson")
    make_scene(ws / "scenes" / "s2_2025-07-01.tif", nir_mean=2600)
    make_scene(ws / "scenes" / "s2_2025-07-15.tif", nir_mean=1400)
    return settings, registry, ctx, ws


def test_report_full_chain(env):
    _settings, reg, ctx, ws = env
    res = reg.call("geo_farm_report", {
        "farm_id": "farm-12",
        "farms_path": "farms.geojson",
        "raster_glob": "scenes/*.tif",
        "band_map": {"green": 1, "red": 3, "nir": 4},
        "out_dir": "runs/reports/farm-12",
    }, ctx)
    assert res.status == "ok", res.error
    val = res.value
    assert len(val["dates"]) == 2
    assert val["trend"]["last"] < val["trend"]["first"]
    assert val["map_png"] and (ws / "runs/reports/farm-12/map.png").exists()
    assert (ws / "runs/reports/farm-12/report.md").exists()
    assert (ws / "runs/reports/farm-12/stats.csv").exists()

    md = (ws / "runs/reports/farm-12/report.md").read_text(encoding="utf-8")
    assert "| date | mean | class |" in md
    assert "2025-07-01" in md and "2025-07-15" in md
    # memory not configured → traceability skipped gracefully
    assert val["memory_ingest"]["ingested"] is False


def test_report_unknown_farm_lists_ids(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_farm_report", {
        "farm_id": "nope", "farms_path": "farms.geojson", "raster_glob": "scenes/*.tif"
    }, ctx)
    assert res.status == "validation_error"
    assert "farm-12" in res.error and "farm-13" in res.error


def test_report_requires_exclusive_selector(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_farm_report", {
        "farm_id": "farm-12", "bbox": [48, 31, 49, 32],
        "farms_path": "farms.geojson", "raster_glob": "scenes/*.tif"
    }, ctx)
    assert res.status == "validation_error"


def test_bbox_mode_selects_intersecting(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_farm_report", {
        "bbox": [48.41, 31.56, 48.44, 31.58],
        "farms_path": "farms.geojson",
        "raster_glob": "scenes/*.tif",
        "band_map": {"green": 1, "red": 3, "nir": 4},
        "out_dir": "runs/reports/bboxsel",
    }, ctx)
    assert res.status == "ok", res.error
    assert res.value["farm_id"] is None


def test_recommend_evidence_pack_from_ndvi(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_recommend", {
        "topic": "irrigation", "farm_id": "farm-12", "ndvi_mean": 0.31,
        "knowledge_query": "water stress irrigation",
    }, ctx)
    assert res.status == "ok", res.error
    val = res.value
    assert val["stress_state"]["stress_label"] == "severe stress"
    assert isinstance(val["hits"], list)
    assert any("knowledge search failed" in g for g in val["gaps"]) or val["hits"]


def test_recommend_gaps_without_evidence(env):
    _settings, reg, ctx, _ws = env
    res = reg.call("geo_recommend", {"topic": "spraying", "farm_id": "farm-12"}, ctx)
    assert res.status == "ok"
    assert any("report_dir or ndvi_mean" in g for g in res.value["gaps"])


def test_recommend_with_report_dir_and_hits(env):
    _settings, reg, ctx, ws = env
    rep_dir = ws / "runs/reports/dummy"
    rep_dir.mkdir(parents=True, exist_ok=True)
    stats_csv = rep_dir / "stats.csv"

    # Register geo_search
    from geoagent.registry import ToolDefinition, ToolResult

    @reg.register(
        ToolDefinition(
            name="geo_search",
            description="search mock",
            params={
                "type": "object",
                "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
            },
        )
    )
    def dummy_search(args, ctx):
        return ToolResult(
            status="ok",
            value={
                "hits": [
                    {
                        "id": "h1",
                        "text": "Sugarcane irrigation manual",
                        "locator": "p. 12",
                        "score": 0.95,
                    }
                ]
            },
        )

    # 1. stats.csv with valid row
    stats_csv.write_text("date,mean_ndvi,stress_class\n2025-07-01,0.45,2\n", encoding="utf-8")

    res = reg.call(
        "geo_recommend",
        {"topic": "irrigation", "farm_id": "farm-12", "report_dir": "runs/reports/dummy"},
        ctx,
    )
    assert res.status == "ok"
    assert res.value["stress_state"]["stress_class"] == "2"
    assert res.value["stress_state"]["stress_label"] == "severe stress"
    assert len(res.value["hits"]) == 1
    assert res.value["hits"][0]["id"] == "h1"

    # 2. stats.csv empty
    stats_csv.write_text("date,mean_ndvi,stress_class\n", encoding="utf-8")
    res_empty = reg.call(
        "geo_recommend",
        {"topic": "irrigation", "farm_id": "farm-12", "report_dir": "runs/reports/dummy"},
        ctx,
    )
    assert any("has no rows" in g for g in res_empty.value["gaps"])

    # 3. stats.csv missing
    stats_csv.unlink()
    res_missing = reg.call(
        "geo_recommend",
        {"topic": "irrigation", "farm_id": "farm-12", "report_dir": "runs/reports/dummy"},
        ctx,
    )
    assert any("no stats.csv under" in g for g in res_missing.value["gaps"])


def test_advisor_error_branches(env):
    settings, reg, ctx, ws = env

    # farms file missing
    res_no_farms = reg.call(
        "geo_farm_report",
        {"farm_id": "farm-12", "farms_path": "nonexistent.geojson", "raster_glob": "scenes/*.tif"},
        ctx,
    )
    assert res_no_farms.status == "validation_error"
    assert "farms file not found" in res_no_farms.error

    # no raster files matched
    res_no_rasters = reg.call(
        "geo_farm_report",
        {"farm_id": "farm-12", "farms_path": "farms.geojson", "raster_glob": "scenes/none_*.tif"},
        ctx,
    )
    assert res_no_rasters.status == "validation_error"
    assert "no raster files matched" in res_no_rasters.error

    # no dates in filenames
    no_date_file = ws / "scenes/undated.tif"
    no_date_file.write_text("fake", encoding="utf-8")
    res_no_dates = reg.call(
        "geo_farm_report",
        {"farm_id": "farm-12", "farms_path": "farms.geojson", "raster_glob": "scenes/undated.tif"},
        ctx,
    )
    assert res_no_dates.status == "validation_error"
    assert "no dates found" in res_no_dates.error

    # _ingest_report with mock memory success & failure
    from unittest.mock import MagicMock, patch

    from geoagent.tools.advisor_tools import _ingest_report

    mock_mem = MagicMock()
    mock_col = MagicMock()
    mock_col.name = "reports"
    mock_col.id = "col_rep"
    mock_mem.list_collections.return_value = [mock_col]
    mock_job = MagicMock()
    mock_job.result = {"asset_id": "ast_123"}
    mock_mem.ingest.return_value = mock_job

    with patch("geoagent.tools.memory_tools._get_memory", return_value=mock_mem):
        ing_res = _ingest_report(settings, ws / "farms.geojson", "reports")
        assert ing_res["ingested"] is True
        assert ing_res["asset_id"] == "ast_123"

        # ingest raises exception
        mock_mem.ingest.side_effect = RuntimeError("ingest failed")
        ing_fail = _ingest_report(settings, ws / "farms.geojson", "reports")
        assert ing_fail["ingested"] is False
        assert "ingest failed" in ing_fail["reason"]

