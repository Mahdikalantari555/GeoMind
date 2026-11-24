"""Regression tests for the download/clip rasterio-windowing path.

The existing fetch tests use a ``FakeFetcher`` or patch out the real work, so
the "clip in the scene's own CRS" fix had no guard. These tests exercise real
``rasterio`` windowing against an in-memory GeoTIFF in a projected (UTM) CRS —
no network and no mocking of the geometry/window logic under test.
"""
from __future__ import annotations

from math import ceil
from pathlib import Path

import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.windows import from_bounds

from data_engine.io.errors import DownloadError
from data_engine.io.planetary_computer_fetcher import (
    PlanetaryComputerLandsatFetcher,
    _enforce_coverage,
)

# An ROI over Khuzestan, Iran. Its centroid (48.05E) falls in UTM zone 39, but
# the Landsat tile grid that covers it is zone 38 (EPSG:32638) — the exact
# mismatch that previously fed a wrong-CRS window into the read and failed with
# ZeroDivisionError.
ROI_BBOX = [47.92, 32.24, 48.19, 32.50]
SCENE_CRS = "EPSG:32638"


def _scene_bounds(bbox: list[float], crs: str) -> tuple[float, float, float, float]:
    return PlanetaryComputerLandsatFetcher()._bounds_in_crs(bbox, crs)


def _memory_scene(bounds: tuple[float, float, float, float], resolution: float = 30.0) -> MemoryFile:
    """Create an in-memory raster whose transform covers ``bounds``."""
    minx, miny, maxx, maxy = bounds
    width = ceil((maxx - minx) / resolution)
    height = ceil((maxy - miny) / resolution)
    transform = from_origin(minx, maxy, resolution, resolution)
    data = np.arange(width * height, dtype="uint16").reshape(height, width)
    memfile = MemoryFile()
    with memfile.open(
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint16",
        crs=SCENE_CRS,
        transform=transform,
        nodata=0,
    ) as dataset:
        dataset.write(data, 1)
    return memfile


def test_projected_bbox_encloses_all_roi_corners() -> None:
    """The bbox must be projected with an 9-point envelope, not 2 diagonals."""
    minx, miny, maxx, maxy = _scene_bounds(ROI_BBOX, SCENE_CRS)
    transformer = Transformer.from_crs("EPSG:4326", SCENE_CRS, always_xy=True)
    for lon, lat in [
        (ROI_BBOX[0], ROI_BBOX[1]),
        (ROI_BBOX[2], ROI_BBOX[1]),
        (ROI_BBOX[2], ROI_BBOX[3]),
        (ROI_BBOX[0], ROI_BBOX[3]),
    ]:
        x, y = transformer.transform(lon, lat)
        assert minx <= x <= maxx
        assert miny <= y <= maxy


def test_window_from_projected_bounds_is_inside_scene() -> None:
    """from_bounds with the scene-CRS bbox yields a finite, in-bounds window."""
    bounds = _scene_bounds(ROI_BBOX, SCENE_CRS)
    memfile = _memory_scene(bounds)
    with memfile.open() as src:
        window = from_bounds(*bounds, src.transform)
        assert np.isfinite(window.col_off)
        assert np.isfinite(window.row_off)
        assert window.width > 0 and window.height > 0
        # The window must sit within the raster's own pixel grid.
        assert window.col_off >= -0.5
        assert window.row_off >= -0.5
        assert window.col_off + window.width <= src.width + 0.5
        assert window.row_off + window.height <= src.height + 0.5
    memfile.close()


def test_clip_read_returns_data_with_correct_transform() -> None:
    """The exact read performed by download_and_clip_bands, end to end."""
    bounds = _scene_bounds(ROI_BBOX, SCENE_CRS)
    memfile = _memory_scene(bounds)
    with memfile.open() as src:
        window = from_bounds(*bounds, src.transform)
        data = src.read(1, window=window)
        out_transform = src.window_transform(window)

        assert data.ndim == 2
        assert data.size > 0
        # The output georeference must match the clipped pixel extent.
        assert out_transform.a == pytest.approx(src.transform.a)
        assert out_transform.e == pytest.approx(src.transform.e)
        # Output extent must be inside the ROI's projected bounds.
        out_bounds = rasterio.transform.array_bounds(data.shape[0], data.shape[1], out_transform)
        assert bounds[0] - 1 <= out_bounds[0] <= bounds[2] + 1
        assert bounds[1] - 1 <= out_bounds[1] <= bounds[3] + 1
    memfile.close()


def test_write_windowed_band_honours_resolution_dtype_and_nodata(tmp_path: Path) -> None:
    """The real write path keeps CRS/dtype/nodata and honours ``resolution``."""
    bounds = _scene_bounds(ROI_BBOX, SCENE_CRS)
    src_path = tmp_path / "scene.tif"
    width = ceil((bounds[2] - bounds[0]) / 30.0)
    height = ceil((bounds[3] - bounds[1]) / 30.0)
    with rasterio.open(
        src_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint16",
        crs=SCENE_CRS,
        transform=from_origin(bounds[0], bounds[3], 30.0, 30.0),
        nodata=0,
    ) as dst:
        dst.write(np.full((height, width), 100, dtype="uint16"), 1)

    fetcher = PlanetaryComputerLandsatFetcher()
    out_path = tmp_path / "red.tif"
    fetcher._write_windowed_band(str(src_path), ROI_BBOX, out_path, size=60.0)

    with rasterio.open(out_path) as src:
        assert src.crs is not None and src.crs.to_string() == SCENE_CRS
        assert src.dtypes == ("uint16",)
        assert src.nodata == 0
        assert src.transform.a == pytest.approx(60.0, rel=0.1)
        out_bounds = rasterio.transform.array_bounds(src.height, src.width, src.transform)
        assert bounds[0] - 30 <= out_bounds[0] <= bounds[2] + 30
        assert bounds[1] - 30 <= out_bounds[1] <= bounds[3] + 30
    assert not out_path.with_name("red.tif.partial").exists()
    assert "red" in fetcher.band_hashes


def test_enforce_coverage_rejects_mostly_nodata_scene(tmp_path: Path) -> None:
    """A scene whose valid-pixel fraction is too low is deleted, not registered."""
    band = tmp_path / "red.tif"
    with rasterio.open(
        band,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="uint16",
        crs=SCENE_CRS,
        transform=from_origin(0, 10, 30, 30),
        nodata=0,
    ) as dst:
        data = np.zeros((10, 10), dtype="uint16")
        data[0, 0] = 100
        dst.write(data, 1)

    with pytest.raises(DownloadError, match="insufficient valid pixel coverage"):
        _enforce_coverage("scene-under-test", [band], 0.9)
    assert not band.exists()
