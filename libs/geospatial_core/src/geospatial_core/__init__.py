"""Unified geospatial core library for remote sensing and GIS calculations."""

from geospatial_core.gis import (
    geodesic_polygon_area_m2,
    parse_epsg,
    polygon_area_deg2,
    polygonize_array,
    reclassify_array,
    zonal_statistics,
)
from geospatial_core.spectral import (
    band_statistics,
    compute_spectral_index,
    evi,
    ndvi,
    ndwi,
    savi,
)

__all__ = [
    "band_statistics",
    "compute_spectral_index",
    "evi",
    "geodesic_polygon_area_m2",
    "ndvi",
    "ndwi",
    "parse_epsg",
    "polygon_area_deg2",
    "polygonize_array",
    "reclassify_array",
    "savi",
    "zonal_statistics",
]
