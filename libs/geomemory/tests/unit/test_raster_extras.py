"""Unit tests for raster spectral indices, tiler, and reader helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from geomemory.core.exceptions import BandMappingError
from geomemory.rs.raster.metadata import RasterSceneData
from geomemory.rs.raster.reader import (
    RasterReader,
    _crs_string,
    _resolution_m,
    _transform_list,
    _wgs84_bounds,
)
from geomemory.rs.raster.spectral import (
    _check_shapes,
    compute_index,
    resolve_bands,
    validate_index,
)
from geomemory.rs.raster.tiler import (
    build_tiles,
    window_bounds,
    window_grid,
    window_only_tiles,
    window_transform,
)


def test_spectral_functions() -> None:
    arr1 = np.ones((10, 10), dtype=np.float32)
    arr2 = np.ones((10, 10), dtype=np.float32) * 2.0
    arr_diff = np.ones((5, 5), dtype=np.float32)

    # _check_shapes
    _check_shapes(arr1, arr2, "test")
    with pytest.raises(ValueError, match="equal-shaped inputs"):
        _check_shapes(arr1, arr_diff, "test")

    # validate_index
    mapping = {"nir": 8, "red": 4}
    assert validate_index("NDVI", mapping, {"nir", "red"}) == mapping
    with pytest.raises(BandMappingError, match="missing"):
        validate_index("NDVI", {"nir": 8}, {"nir", "red"})

    # compute_index NDVI & EVI
    arrays = {
        "nir": np.ones((10, 10), dtype=np.float32) * 0.5,
        "red": np.ones((10, 10), dtype=np.float32) * 0.2,
        "blue": np.ones((10, 10), dtype=np.float32) * 0.1,
    }
    ndvi_res = compute_index("NDVI", arrays, {"nir": 8, "red": 4}, {"nir", "red"})
    assert ndvi_res.shape == (10, 10)
    evi_res = compute_index("EVI", arrays, {"nir": 8, "red": 4, "blue": 2}, {"nir", "red", "blue"})
    assert evi_res.shape == (10, 10)

    # unsupported index
    with pytest.raises(BandMappingError, match="Unsupported spectral index"):
        compute_index("UNKNOWN", arrays, {"nir": 8}, {"nir"})

    # resolve_bands valid and error
    scene = RasterSceneData(bands=[{"index": 1, "name": "B1"}, {"index": 2, "name": "B2"}])
    assert resolve_bands(scene, {"nir": 2}) == {"nir": 2}
    with pytest.raises(BandMappingError, match="out of range"):
        resolve_bands(scene, {"nir": 5})


def test_tiler_functions(tmp_path: Path) -> None:
    assert window_grid(0, 100) == []
    assert window_grid(100, -1) == []
    assert window_transform([1.0, 2.0], {"x": 0, "y": 0}) == []
    assert window_bounds([1.0, 2.0], {"x": 0, "y": 0, "width": 10, "height": 10}) == (0.0, 0.0, 0.0, 0.0)

    scene = RasterSceneData(
        width=200,
        height=200,
        crs="EPSG:4326",
        transform=[0.001, 0.0, 10.0, 0.0, -0.001, 20.0],
    )

    # window_only_tiles with EPSG:4326
    tiles = window_only_tiles(scene, tile_size=100)
    assert len(tiles) == 4
    assert tiles[0].footprint is not None

    # build_tiles with mock reader and preview generation
    class MockReader:
        def read_window(self, source_path: str | Path, window: dict[str, int]) -> np.ndarray:
            return np.ones((3, 50, 50), dtype=np.float32) * 100

    built_tiles = build_tiles(scene, "fake.tif", tmp_path, reader=MockReader(), tile_size=100)
    assert len(built_tiles) == 4
    assert built_tiles[0].preview_path is not None
    assert Path(built_tiles[0].preview_path).is_file()

    # build_tiles with failing reader
    class FailingReader:
        def read_window(self, source_path: str | Path, window: dict[str, int]) -> np.ndarray:
            raise RuntimeError("Corrupt data")

    fail_tiles = build_tiles(scene, "fake.tif", tmp_path, reader=FailingReader(), tile_size=100)
    assert len(fail_tiles) == 4
    assert fail_tiles[0].preview_path is None


def test_reader_helpers() -> None:
    # _crs_string
    assert _crs_string(None) == "EPSG:4326"
    assert _crs_string("4326") == "EPSG:4326"
    assert _crs_string("EPSG:32631") == "EPSG:32631"

    obj_with_epsg = MagicMock()
    obj_with_epsg.to_epsg.return_value = 32632
    assert _crs_string(obj_with_epsg) == "EPSG:32632"

    obj_with_str = MagicMock()
    obj_with_str.to_epsg.return_value = None
    obj_with_str.to_string.return_value = "EPSG:3857"
    assert _crs_string(obj_with_str) == "EPSG:3857"

    obj_unknown = MagicMock()
    obj_unknown.to_epsg.return_value = None
    obj_unknown.to_string.return_value = "unrecognized"
    assert _crs_string(obj_unknown) == "EPSG:4326"

    # _wgs84_bounds
    assert _wgs84_bounds("EPSG:4326", (1.0, 2.0, 3.0, 4.0)) == (1.0, 2.0, 3.0, 4.0)
    # reproject from EPSG:3857
    bounds_4326 = _wgs84_bounds("EPSG:3857", (100000.0, 100000.0, 200000.0, 200000.0))
    assert len(bounds_4326) == 4

    # _transform_list
    assert _transform_list(None) == []
    assert _transform_list([1.0, 0.0, 10.0, 0.0, -1.0, 20.0]) == [1.0, 0.0, 10.0, 0.0, -1.0, 20.0]

    # _transform_list affine object
    class AffineMock:
        a, b, c, d, e, f = 1.0, 2.0, 3.0, 4.0, 5.0, 6.0
    assert _transform_list(AffineMock()) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    # _resolution_m
    assert _resolution_m(None, "EPSG:4326") is None
    res_deg = _resolution_m([0.001, 0.0, 0.0, 0.0, -0.001, 0.0], "EPSG:4326")
    assert res_deg is not None and abs(res_deg - 111.32) < 0.1
    res_utm = _resolution_m([10.0, 0.0, 0.0, 0.0, -10.0, 0.0], "EPSG:32631")
    assert res_utm == 10.0

    # RasterReader.read_all, read_window, read_scene
    mock_backend = MagicMock()
    mock_ds = MagicMock()
    mock_ds.read.return_value = np.zeros((3, 20, 20), dtype=np.uint8)
    mock_ds.crs = "EPSG:4326"
    mock_ds.bounds = (10.0, 20.0, 11.0, 21.0)
    mock_ds.tags.return_value = {"SPACECRAFT_NAME": "Sentinel-2"}
    mock_ds.count = 1
    mock_ds.dtypes = ["uint16"]
    mock_ds.width = 100
    mock_ds.height = 100
    mock_ds.transform = [0.01, 0.0, 10.0, 0.0, -0.01, 21.0]
    mock_ds.descriptions = ["B1"]
    mock_ds.nodata = 0
    mock_backend.open.return_value = mock_ds

    reader = RasterReader(backend=mock_backend)
    arr = reader.read_all("fake.tif")
    assert arr.shape == (3, 20, 20)
    arr_win = reader.read_window("fake.tif", {"x": 0, "y": 0, "width": 10, "height": 10})
    assert arr_win.shape == (3, 20, 20)
    scene_data = reader.read_scene("fake.tif")
    assert scene_data.crs == "EPSG:4326"
    assert scene_data.width == 100
