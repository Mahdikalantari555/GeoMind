"""Unit tests for geospatial_core."""

import numpy as np
import pytest

from geospatial_core import (
    band_statistics,
    compute_spectral_index,
    evi,
    geodesic_polygon_area_m2,
    ndvi,
    ndwi,
    parse_epsg,
    polygon_area_deg2,
    reclassify_array,
    savi,
    zonal_statistics,
)


def test_ndvi_basic_and_nodata() -> None:
    nir = np.array([0.8, 0.5, 0.0])
    red = np.array([0.2, 0.5, 0.0])
    result = ndvi(nir, red)
    assert np.isclose(result[0], (0.8 - 0.2) / (0.8 + 0.2))
    assert np.isclose(result[1], 0.0)
    assert np.isnan(result[2])  # zero division protected


def test_evi_basic() -> None:
    nir = np.array([0.8, 0.5])
    red = np.array([0.2, 0.5])
    blue = np.array([0.1, 0.2])
    result = evi(nir, red, blue)
    assert np.isfinite(result[0])
    assert np.isfinite(result[1])


def test_ndwi_and_savi() -> None:
    green = np.array([0.3, 0.1])
    nir = np.array([0.7, 0.8])
    red = np.array([0.2, 0.3])
    idx_ndwi = ndwi(green, nir)
    assert np.isclose(idx_ndwi[0], (0.3 - 0.7) / (0.3 + 0.7))

    idx_savi = savi(red, nir, light_coeff=0.5)
    assert np.isclose(idx_savi[0], ((0.7 - 0.2) / (0.7 + 0.2 + 0.5)) * 1.5)


def test_compute_spectral_index_dispatch() -> None:
    bands = {
        "nir": np.array([0.8]),
        "red": np.array([0.2]),
        "green": np.array([0.3]),
        "blue": np.array([0.1]),
    }
    for name in ["NDVI", "EVI", "NDWI", "SAVI"]:
        res = compute_spectral_index(name, bands)
        assert np.isfinite(res[0])

    with pytest.raises(ValueError, match="Unsupported spectral index"):
        compute_spectral_index("UNKNOWN_INDEX", bands)


def test_band_statistics() -> None:
    arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, np.nan])
    stats = band_statistics(arr)
    assert stats["count"] == 5.0
    assert stats["min"] == 1.0
    assert stats["max"] == 5.0
    assert stats["mean"] == 3.0


def test_reclassify_array() -> None:
    data = np.array([[0.1, 0.35], [0.65, 0.9]])
    rules = [
        {"min": 0.0, "max": 0.3, "out": 1},
        {"min": 0.3, "max": 0.6, "out": 2},
        {"min": 0.6, "max": 1.0, "out": 3},
    ]
    reclassed, hist = reclassify_array(data, rules)
    assert reclassed[0, 0] == 1
    assert reclassed[0, 1] == 2
    assert reclassed[1, 0] == 3
    assert reclassed[1, 1] == 3
    assert hist["3"] == 2
    assert hist["1"] == 1
    assert hist["2"] == 1


def test_reclassify_overlapping_error() -> None:
    data = np.array([[0.2]])
    rules = [
        {"min": 0.0, "max": 0.5, "out": 1},
        {"min": 0.4, "max": 0.8, "out": 2},
    ]
    with pytest.raises(ValueError, match="Overlapping"):
        reclassify_array(data, rules)


def test_area_calculations() -> None:
    square = {
        "type": "Polygon",
        "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
    }
    deg2 = polygon_area_deg2(square)
    assert np.isclose(deg2, 1.0)

    m2 = geodesic_polygon_area_m2(square)
    assert m2 > 1e10  # ~1.23e10 m^2 around equator


def test_zonal_statistics() -> None:
    zone = np.array([10.0, 20.0, 30.0, -9999.0])
    stats = zonal_statistics(zone, nodata=-9999.0)
    assert stats["count"] == 3.0
    assert stats["mean"] == 20.0
    assert stats["nodata_share"] == 0.25


def test_parse_epsg() -> None:
    assert parse_epsg(4326) == 4326
    assert parse_epsg("EPSG:32639") == 32639
    assert parse_epsg("3857") == 3857
    assert parse_epsg(None) is None
