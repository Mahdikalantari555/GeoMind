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
    polygonize_array,
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
    assert parse_epsg("INVALID_EPSG") is None

    class MockCRS:
        def __init__(self, epsg: int | None):
            self._epsg = epsg

        def to_epsg(self) -> int | None:
            return self._epsg

    assert parse_epsg(MockCRS(4326)) == 4326
    assert parse_epsg(MockCRS(None)) is None


def test_polygonize_array_basic_and_mask_nodata() -> None:
    import rasterio.transform

    data = np.array([[1, 1, 0], [1, 2, 0], [0, 0, 0]], dtype=np.int32)
    affine = rasterio.transform.from_origin(0.0, 10.0, 1.0, 1.0)

    # With nodata
    feats = polygonize_array(data, transform=affine, nodata=0)
    assert len(feats) >= 2
    classes = {f["properties"]["class"] for f in feats}
    assert 1 in classes
    assert 2 in classes
    assert 0 not in classes

    # With explicit mask and simplify_tolerance
    mask = data > 0
    feats_simp = polygonize_array(data, transform=affine, mask=mask, simplify_tolerance=0.01)
    assert len(feats_simp) >= 2
    for f in feats_simp:
        assert "geometry" in f
        assert f["properties"]["area_deg2"] > 0

    # With default mask (mask=None, nodata=None)
    feats_all = polygonize_array(data, transform=affine)
    assert len(feats_all) >= 2


def test_polygon_area_multipolygon_and_3d_and_holes() -> None:
    multipoly = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0.0, 0.0, 10.0], [1.0, 0.0, 10.0], [1.0, 1.0, 10.0], [0.0, 1.0, 10.0], [0.0, 0.0, 10.0]]],
            [[[2.0, 2.0, 5.0], [3.0, 2.0, 5.0], [3.0, 3.0, 5.0], [2.0, 3.0, 5.0], [2.0, 2.0, 5.0]]],
        ],
    }
    deg2 = polygon_area_deg2(multipoly)
    assert np.isclose(deg2, 2.0)

    m2 = geodesic_polygon_area_m2(multipoly)
    assert m2 > 2e10

    # Polygon with a hole
    donut = {
        "type": "Polygon",
        "coordinates": [
            # exterior 10x10 = 100
            [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]],
            # hole 2x2 = 4
            [[2.0, 2.0], [4.0, 2.0], [4.0, 4.0], [2.0, 4.0], [2.0, 2.0]],
        ],
    }
    donut_deg2 = polygon_area_deg2(donut)
    assert np.isclose(donut_deg2, 96.0)

    donut_m2 = geodesic_polygon_area_m2(donut)
    assert donut_m2 > 0

    # Empty and degenerate coordinates
    assert polygon_area_deg2({"type": "Polygon", "coordinates": []}) == 0.0
    assert polygon_area_deg2({"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 1.0]]]}) == 0.0
    assert geodesic_polygon_area_m2({"type": "Polygon", "coordinates": []}) == 0.0
    assert geodesic_polygon_area_m2({"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 1.0]]]}) == 0.0


def test_spectral_edge_branches() -> None:
    bands = {
        "nir": np.array([0.8]),
        "red": np.array([0.2]),
        "blue": np.array([0.1]),
        "green": np.array([0.3]),
    }
    evi_res = compute_spectral_index("EVI", bands, g=2.0, c1=5.0, c2=6.0, light=0.8)
    assert np.isfinite(evi_res[0])

    savi_res = compute_spectral_index("SAVI", bands, savi_l=0.4)
    assert np.isfinite(savi_res[0])

    # Shape mismatch error
    with pytest.raises(ValueError, match="equal-shaped"):
        ndvi(np.array([1.0, 2.0]), np.array([1.0]))

    # Empty band statistics
    empty_stats = band_statistics(np.array([]))
    assert empty_stats["count"] == 0.0

    all_nan_stats = band_statistics(np.array([np.nan, np.nan]))
    assert all_nan_stats["count"] == 0.0



def test_zonal_statistics_empty() -> None:
    empty = np.array([])
    stats = zonal_statistics(empty)
    assert stats["count"] == 0.0
    assert stats["nodata_share"] == 0.0

    all_nodata = np.array([-9999.0, -9999.0])
    stats_nodata = zonal_statistics(all_nodata, nodata=-9999.0)
    assert stats_nodata["count"] == 0.0
    assert stats_nodata["nodata_share"] == 1.0

