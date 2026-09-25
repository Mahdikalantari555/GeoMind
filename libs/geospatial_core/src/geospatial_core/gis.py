"""Core GIS calculations: zonal statistics, polygonization, reclassification, area, CRS helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np


def reclassify_array(
    data: np.ndarray,
    rules: Sequence[dict[str, float | int]],
    nodata_in: float | None = None,
    nodata_out: int = -9999,
) -> tuple[np.ndarray, dict[str, int]]:
    """Reclassify numeric 2D array based on half-open intervals [min, max) -> out value.

    Returns:
        tuple of (reclassified array as int32, histogram dict of class counts).
    """
    sorted_rules = sorted(rules, key=lambda r: float(r["min"]))
    for i in range(len(sorted_rules) - 1):
        if float(sorted_rules[i]["max"]) > float(sorted_rules[i + 1]["min"]):
            raise ValueError(
                f"Overlapping rules: [{sorted_rules[i]['min']},{sorted_rules[i]['max']}) "
                f"vs [{sorted_rules[i+1]['min']},{sorted_rules[i+1]['max']})"
            )

    arr = np.asarray(data, dtype=np.float64)
    if nodata_in is not None:
        valid = np.isfinite(arr) & (arr != nodata_in)
    else:
        valid = np.isfinite(arr)

    out = np.full(arr.shape, nodata_out, dtype=np.int32)
    for rule in sorted_rules:
        r_min = float(rule["min"])
        r_max = float(rule["max"])
        r_val = int(rule["out"])
        mask = valid & (arr >= r_min) & (arr < r_max)
        out[mask] = r_val

    valid_vals = out[out != nodata_out]
    if valid_vals.size > 0:
        vals, counts = np.unique(valid_vals, return_counts=True)
        histogram = {str(int(v)): int(c) for v, c in zip(vals, counts, strict=False)}
    else:
        histogram = {}

    return out, histogram


def polygon_area_deg2(geom: dict[str, Any]) -> float:
    """Calculate planar area in square degrees using Shoelace formula."""
    rings: list[list[Sequence[float]]] = []
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])
    if geom_type == "Polygon":
        if coords:
            rings = [coords[0]]
    elif geom_type == "MultiPolygon":
        rings = [poly[0] for poly in coords if poly]

    total = 0.0
    for ring in rings:
        pts = list(ring)
        if len(pts) < 3:
            continue
        s = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=False):
            s += float(x1) * float(y2) - float(x2) * float(y1)
        total += abs(s) / 2.0
    return total


def geodesic_polygon_area_m2(geom: dict[str, Any]) -> float:
    """Approximate geodesic area in square meters using spherical approximation (WGS84 mean radius R=6371008.8m)."""
    r_earth = 6371008.8
    rings: list[list[Sequence[float]]] = []
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])
    if geom_type == "Polygon":
        if coords:
            rings = [coords[0]]
    elif geom_type == "MultiPolygon":
        rings = [poly[0] for poly in coords if poly]

    total_steradians = 0.0
    for ring in rings:
        pts = list(ring)
        if len(pts) < 3:
            continue
        # spherical excess using l'Huilier or line integral in radians
        rad_pts = [(math.radians(p[0]), math.radians(p[1])) for p in pts]
        s = 0.0
        for i in range(len(rad_pts)):
            lon1, lat1 = rad_pts[i]
            lon2, lat2 = rad_pts[(i + 1) % len(rad_pts)]
            s += (lon2 - lon1) * (2.0 + math.sin(lat1) + math.sin(lat2))
        total_steradians += abs(s) / 2.0

    return total_steradians * (r_earth**2)


def polygonize_array(
    data: np.ndarray,
    transform: Any,
    mask: np.ndarray | None = None,
    nodata: float | None = None,
    simplify_tolerance: float | None = None,
) -> list[dict[str, Any]]:
    """Polygonize raster array to GeoJSON features with class value and area."""
    import rasterio.features

    arr = np.asarray(data)
    if mask is None:
        if nodata is not None:
            mask = arr != nodata
        else:
            mask = np.ones(arr.shape, dtype=bool)

    geoms = rasterio.features.shapes(arr, mask=mask, transform=transform)
    features: list[dict[str, Any]] = []

    for geom, value in geoms:
        shape_geom = geom
        if simplify_tolerance is not None:
            import shapely.geometry
            shape_obj = shapely.geometry.shape(geom).simplify(simplify_tolerance)
            shape_geom = shapely.geometry.mapping(shape_obj)

        area = polygon_area_deg2(shape_geom)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "class": int(value),
                    "area_deg2": round(area, 6),
                },
                "geometry": shape_geom,
            }
        )
    return features


def zonal_statistics(
    data: np.ndarray,
    nodata: float | None = None,
) -> dict[str, float]:
    """Calculate summary statistics over an extracted raster array zone."""
    values = np.asarray(data, dtype=np.float64).ravel()
    if nodata is not None:
        valid = np.isfinite(values) & (values != nodata)
    else:
        valid = np.isfinite(values)

    finite = values[valid]
    total_count = float(values.size)
    if finite.size == 0 or total_count == 0:
        return {
            "count": 0.0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "p05": 0.0,
            "p95": 0.0,
            "nodata_share": 1.0 if total_count > 0 else 0.0,
        }

    return {
        "count": float(finite.size),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "p05": float(np.percentile(finite, 5)),
        "p95": float(np.percentile(finite, 95)),
        "nodata_share": float((total_count - finite.size) / total_count),
    }


def parse_epsg(crs_input: Any) -> int | None:
    """Extract EPSG code from integer, string (e.g. 'EPSG:4326', '4326') or rasterio/pyproj CRS."""
    if crs_input is None:
        return None
    if isinstance(crs_input, int):
        return crs_input
    if hasattr(crs_input, "to_epsg"):
        code = crs_input.to_epsg()
        if code is not None:
            return int(code)
    crs_str = str(crs_input).strip().upper()
    if crs_str.startswith("EPSG:"):
        crs_str = crs_str.split(":", 1)[1]
    if crs_str.isdigit():
        return int(crs_str)
    return None
