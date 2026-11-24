"""Regression tests for scientifically usable fetch/physics inputs.

Covers D-041 (DN→reflectance), D-042 (one shared QA helper) and D-043/044
(correct cloud-coverage metric + Sentinel SCL masking).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
import rasterio
import xarray as xr
from rasterio.transform import from_origin

from data_engine.core.datacube import DataCube
from data_engine.io.landsat_reader import LandsatReader
from data_engine.io.planetary_computer_fetcher import (
    PlanetaryComputerLandsatFetcher,
    SentinelPlanetaryComputerFetcher,
)
from data_engine.pipeline.metric_pipeline import METRICPipeline
from data_engine.preprocess.cloud_mask import CloudMasker


def _item_with_scaling() -> Mock:
    """STAC item whose reflectance assets declare ``raster:bands`` scaling."""
    item = Mock()
    item.id = "LC08_L2SP_166038_20230427_20230428_02_T1"
    item.datetime = None
    item.geometry = {
        "type": "Polygon",
        "coordinates": [
            [[48.0, 31.0], [48.5, 31.0], [48.5, 31.5], [48.0, 31.5], [48.0, 31.0]]
        ],
    }
    item.bbox = [48.0, 31.0, 48.5, 31.5]
    item.collection_id = "landsat-c2-l2"
    blue = Mock()
    blue.properties = {"raster:bands": [{"scale": 2.75e-5, "offset": -0.2}]}
    qa = Mock()
    qa.properties = {}
    item.assets = {"blue": blue, "qa_pixel": qa}
    item.properties = {
        "datetime": "2023-04-27T10:30:00Z",
        "eo:cloud_cover": 5.0,
        "platform": "landsat-8",
    }
    return item


def test_mtl_persists_raster_band_scaling(tmp_path: Path) -> None:
    mtl_path = PlanetaryComputerLandsatFetcher()._create_mtl_metadata(
        _item_with_scaling(), tmp_path
    )
    payload = json.loads(mtl_path.read_text())
    assert payload["band_scaling"]["blue"]["scale"] == pytest.approx(2.75e-5)
    assert payload["band_scaling"]["blue"]["offset"] == pytest.approx(-0.2)
    # QA bands must not receive reflectance scaling.
    assert "qa_pixel" not in payload["band_scaling"]


def test_s2_mtl_persists_raster_band_scaling(tmp_path: Path) -> None:
    item = _item_with_scaling()
    blue = Mock()
    blue.properties = {"raster:bands": [{"scale": 1e-4, "offset": -0.1}]}
    item.assets = {"B02": blue}
    mtl_path = SentinelPlanetaryComputerFetcher()._create_mtl_metadata(item, tmp_path)
    payload = json.loads(mtl_path.read_text())
    assert payload["band_scaling"]["blue"]["scale"] == pytest.approx(1e-4)


def test_dn_to_reflectance_conversion(tmp_path: Path) -> None:
    """A DN of 10000 with scale 2.75e-5 / offset -0.2 yields 0.075."""
    scene = tmp_path / "scene"
    scene.mkdir()
    with rasterio.open(
        scene / "blue.tif",
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="uint16",
        crs="EPSG:32638",
        transform=from_origin(0, 20, 30, 30),
        nodata=0,
    ) as dst:
        dst.write(np.full((2, 2), 10000, dtype="uint16"), 1)
    (scene / "MTL.json").write_text(
        json.dumps(
            {
                "item_id": "test",
                "datetime": "2023-04-27",
                "band_scaling": {"blue": {"scale": 2.75e-5, "offset": -0.2}},
            }
        )
    )

    cube = LandsatReader(band_mapping={"blue": "blue.tif"}).load(str(scene))
    blue = cube.get("blue")
    assert blue is not None
    np.testing.assert_allclose(blue.values, np.full((2, 2), 0.075), rtol=1e-5)
    assert blue.attrs["scale_factor"] == pytest.approx(2.75e-5)


def test_shared_qa_and_scl_validity_helpers() -> None:
    """QA uses dilated=1/cloud=3/shadow=4; SCL masks cloud/shadow classes."""
    qa = np.array([0, 1 << 1, 1 << 3, 1 << 4, 1 << 2], dtype=np.uint16)
    np.testing.assert_array_equal(
        CloudMasker.valid_from_qa(qa), np.array([True, False, False, False, True])
    )
    scl = np.array([4, 5, 3, 8, 9, 11], dtype=np.uint8)
    np.testing.assert_array_equal(
        CloudMasker.valid_from_scl(scl), np.array([True, True, False, False, False, False])
    )


def test_cloud_coverage_reports_cloud_fraction_not_clear_fraction() -> None:
    """Regression for the inverted METRIC cloud-coverage metric (D-043)."""
    cube = DataCube()
    qa = xr.DataArray(np.zeros((2, 2), dtype=np.uint16), dims=["y", "x"])
    cube.add("qa_pixel", qa)

    # 3 clear + 1 cloud: correct coverage is 0.25; the old inverted code
    # reported 0.75 and rejected mostly-clear scenes.
    known_mask = xr.DataArray(
        np.array([[True, True], [True, False]]), dims=["y", "x"]
    )
    pipeline = METRICPipeline(config={})
    pipeline.data = cube
    with (
        patch.object(pipeline, "clip_to_roi"),
        patch.object(CloudMasker, "create_mask", return_value=known_mask),
    ):
        pipeline.preprocess()

    assert pipeline._cloud_coverage == pytest.approx(0.25)
