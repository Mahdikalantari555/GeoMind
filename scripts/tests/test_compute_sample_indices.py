"""Tests for scripts/compute_sample_indices.py."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import Polygon

import scripts.compute_sample_indices as csi


@pytest.fixture
def sample_geojson(tmp_path: Path) -> Path:
    poly = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [51.0, 35.0],
                            [51.5, 35.0],
                            [51.5, 35.5],
                            [51.0, 35.5],
                            [51.0, 35.0],
                        ]
                    ],
                },
            }
        ],
    }
    path = tmp_path / "aoi.geojson"
    path.write_text(json.dumps(poly))
    return path


def test_parse_args_all_options():
    args = csi.parse_args([
        "--input", "aoi.geojson",
        "--dates", "2023-01-01", "2023-02-01", "2023-03-01",
        "--landsat",
        "--sentinel",
        "--resolution", "20.0",
    ])
    assert args.input == "aoi.geojson"
    assert args.dates == ["2023-01-01", "2023-02-01", "2023-03-01"]
    assert args.landsat is True
    assert args.sentinel is True
    assert args.resolution == 20.0


def test_parse_args_defaults():
    args = csi.parse_args([
        "--input", "aoi.geojson",
        "--dates", "2023-01-01", "2023-02-01", "2023-03-01",
    ])
    assert args.landsat is False
    assert args.sentinel is False
    assert args.resolution == 30.0


def test_date_windows():
    dates = ["2023-06-15", "2023-07-15", "2023-08-15"]
    windows = csi.date_windows(dates)
    assert len(windows) == 3
    for (start, end), date_str in zip(windows, dates):
        target = datetime.fromisoformat(date_str)
        assert (end - start).days == 30
        assert (target - start).days == 15
        assert (end - target).days == 15


def test_load_aoi(sample_geojson: Path):
    geom, bbox = csi.load_aoi(sample_geojson)
    assert isinstance(geom, Polygon)
    assert bbox == [51.0, 35.0, 51.5, 35.5]


def test_load_aoi_errors(tmp_path: Path):
    empty_fc = tmp_path / "empty.geojson"
    empty_fc.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
    with pytest.raises(ValueError, match="no features"):
        csi.load_aoi(empty_fc)

    no_geom = tmp_path / "no_geom.geojson"
    no_geom.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature"}]}))
    with pytest.raises(ValueError, match="no geometry"):
        csi.load_aoi(no_geom)


@patch("scripts.compute_sample_indices._run_landsat_pipeline")
@patch("scripts.compute_sample_indices._fetch_scenes")
def test_landsat_path(mock_fetch, mock_pipeline, tmp_path: Path, sample_geojson: Path):
    scene_dir = tmp_path / "work" / "LC08_01"
    scene_dir.mkdir(parents=True)
    mock_fetch.return_value = [{"scene_id": "LC08_01", "directory": str(scene_dir)}]

    def fake_pipeline(scene_dir_p, output_dir, aoi_path):
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "ndvi.tif").touch()

    mock_pipeline.side_effect = fake_pipeline

    ret = csi.main([
        "--input", str(sample_geojson),
        "--dates", "2023-06-01", "2023-07-01", "2023-08-01",
        "--landsat",
    ])
    assert ret == 0
    assert mock_fetch.call_count == 3
    assert mock_pipeline.call_count == 3


@patch("scripts.compute_sample_indices._write_sentinel_outputs")
@patch("scripts.compute_sample_indices._compute_sentinel_indices")
@patch("scripts.compute_sample_indices._load_sentinel_cube")
@patch("scripts.compute_sample_indices._fetch_scenes")
def test_sentinel_path(
    mock_fetch,
    mock_load_cube,
    mock_compute,
    mock_write_outputs,
    tmp_path: Path,
    sample_geojson: Path,
):
    scene_dir = tmp_path / "work" / "S2A_01"
    scene_dir.mkdir(parents=True)
    mock_fetch.return_value = [{"scene_id": "S2A_01", "directory": str(scene_dir)}]
    mock_load_cube.return_value = MagicMock()
    mock_compute.return_value = MagicMock()

    out_file = tmp_path / "output" / "S2A_01-s2" / "ndvi_S2A_01.tif"
    mock_write_outputs.return_value = [out_file]

    ret = csi.main([
        "--input", str(sample_geojson),
        "--dates", "2023-06-01", "2023-07-01", "2023-08-01",
        "--sentinel",
    ])
    assert ret == 0
    assert mock_fetch.call_count == 3
    assert mock_load_cube.call_count == 3
    assert mock_compute.call_count == 3
    assert mock_write_outputs.call_count == 3


@patch("scripts.compute_sample_indices._fetch_scenes")
def test_no_scenes_found_raises_system_exit(mock_fetch, sample_geojson: Path):
    mock_fetch.return_value = []
    dates = ["2023-01-01", "2023-02-01", "2023-03-01"]
    with pytest.raises(SystemExit) as exc_info:
        csi.main([
            "--input", str(sample_geojson),
            "--dates", *dates,
            "--landsat",
        ])
    assert "No scene intersects AOI" in str(exc_info.value)
    for d in dates:
        assert d in str(exc_info.value)
