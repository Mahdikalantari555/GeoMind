"""Core GIS calculations: zonal statistics, polygonization, reclassification, area, CRS helpers."""

from __future__ import annotations

import math
import re
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
    for r in rules:
        if float(r["min"]) >= float(r["max"]):
            raise ValueError(
                f"Invalid rule interval: min ({r['min']}) must be < max ({r['max']})"
            )
        out_val = float(r["out"])
        if not out_val.is_integer():
            raise ValueError(
                f"Invalid class value {r['out']}: class codes must be integers"
            )
        if int(out_val) == int(nodata_out):
            raise ValueError(
                f"Class value {r['out']} collides with the nodata sentinel {nodata_out}; "
                "those pixels would disappear from the histogram"
            )
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
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])
    polys: list[list[Sequence[Sequence[float]]]] = []
    if geom_type == "Polygon":
        if coords:
            polys = [coords]
    elif geom_type == "MultiPolygon":
        polys = [p for p in coords if p]
    elif geom_type not in ("", "Feature"):
        raise ValueError(f"polygon_area_deg2 expects Polygon/MultiPolygon, got {geom_type!r}")

    def _ring_area(ring: Sequence[Sequence[float]]) -> float:
        pts = list(ring)
        if len(pts) < 3:
            return 0.0
        s = 0.0
        for p1, p2 in zip(pts, pts[1:] + pts[:1], strict=False):
            s += float(p1[0]) * float(p2[1]) - float(p2[0]) * float(p1[1])
        return abs(s) / 2.0

    total = 0.0
    for poly in polys:
        if not poly:
            continue
        exterior_area = _ring_area(poly[0])
        holes_area = sum(_ring_area(h) for h in poly[1:])
        if holes_area > exterior_area + 1e-12:
            raise ValueError(
                f"Invalid polygon: holes ({holes_area:.6g} deg²) exceed the exterior ring "
                f"({exterior_area:.6g} deg²)"
            )
        total += exterior_area - holes_area
    return total


def _unwrap_longitudes(lons: list[float]) -> list[float]:
    """Remove 360° jumps so a ring can run across the antimeridian.

    Raw GeoJSON longitudes jump from +179.9 to -179.9, which every
    lon/lat shoelace formula reads as a ~360° sweep and turns a 20 km-wide
    box into half the planet.
    """
    out: list[float] = []
    for lon in lons:
        if not out:
            out.append(lon)
            continue
        prev = out[-1]
        while lon - prev > 180.0:
            lon -= 360.0
        while lon - prev < -180.0:
            lon += 360.0
        out.append(lon)
    return out


def _ring_is_self_intersecting(pts: list[tuple[float, float]]) -> bool:
    """True when two non-adjacent ring edges cross (O(n²), rings are small)."""

    def orient(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))

    def on_segment(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
        return bool(
            min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])
        )

    def intersects(
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
        p4: tuple[float, float],
    ) -> bool:
        d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
        d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
        return (
            (d1 == 0 and on_segment(p3, p4, p1))
            or (d2 == 0 and on_segment(p3, p4, p2))
            or (d3 == 0 and on_segment(p1, p2, p3))
            or (d4 == 0 and on_segment(p1, p2, p4))
        )

    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            if intersects(a, b, pts[j], pts[(j + 1) % n]):
                return True
    return False


def geodesic_polygon_area_m2(geom: dict[str, Any]) -> float:
    """Spherical excess area in square meters (WGS84 mean radius R=6371008.8 m).

    Uses the Green's-theorem form for a sphere::

        A = R²/2 · Σ (λ₂−λ₁)(sin φ₁ + sin φ₂)

    with longitudes unwrapped across the antimeridian. The previous version
    summed ``(2 + sinφ₁ + sinφ₂)``, the band formula for a *zone* between two
    parallels rather than a closed ring. For closed rings the extra ``2`` cancels
    (Δλ sums to zero), so ordinary polygons were unaffected, but any ring the
    code fails to close — or one that crosses the antimeridian — was read as a
    sweep around the globe: a 0.2°×0.2° box straddling 180° reported 889,737 km²
    instead of ~493 km².
    """
    r_earth = 6371008.8
    geom_type = geom.get("type", "")
    coords = geom.get("coordinates", [])
    polys: list[list[Sequence[Sequence[float]]]] = []
    if geom_type == "Polygon":
        if coords:
            polys = [coords]
    elif geom_type == "MultiPolygon":
        polys = [p for p in coords if p]

    def _ring_area_m2(ring: Sequence[Sequence[float]]) -> float:
        pts = [(float(p[0]), float(p[1])) for p in ring]
        if len(pts) < 3:
            return 0.0
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        if len(pts) < 3:
            return 0.0
        if _ring_is_self_intersecting(pts):
            raise ValueError("Invalid polygon ring: self-intersecting (bow-tie) outline")
        unwrapped = _unwrap_longitudes([p[0] for p in pts])
        rad = [
            (math.radians(lon), math.radians(lat))
            for lon, (_, lat) in zip(unwrapped, pts, strict=True)
        ]
        total = 0.0
        n = len(rad)
        for i in range(n):
            lon1, lat1 = rad[i]
            lon2, lat2 = rad[(i + 1) % n]
            total += (lon2 - lon1) * (math.sin(lat1) + math.sin(lat2))
        return abs(total) / 2.0 * (r_earth**2)

    total_m2 = 0.0
    for poly in polys:
        if not poly:
            continue
        exterior_area = _ring_area_m2(poly[0])
        holes_area = sum(_ring_area_m2(h) for h in poly[1:])
        if holes_area > exterior_area + 1.0:
            raise ValueError(
                f"Invalid polygon: holes ({holes_area:.0f} m²) exceed the exterior ring "
                f"({exterior_area:.0f} m²)"
            )
        total_m2 += exterior_area - holes_area
    return total_m2


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


#: Sentinel written by `reclassify_array` and by the raster writers in the
#: agent tools; a zone that contains it must not average it in.
DEFAULT_NODATA = -9999.0


def zonal_statistics(
    data: np.ndarray,
    nodata: float | None = None,
) -> dict[str, float | None]:
    """Calculate summary statistics over an extracted raster array zone.

    When ``nodata`` is not supplied the canonical ``-9999`` sentinel is
    excluded, matching what the raster writers emit. An all-nodata or empty
    zone reports ``count = 0`` and ``mean = nodata`` (``None``) rather than a
    fabricated ``0.0`` mean.
    """
    values = np.asarray(data, dtype=np.float64).ravel()
    sentinel = DEFAULT_NODATA if nodata is None else nodata
    valid = np.isfinite(values) & (values != sentinel)

    finite = values[valid]
    total_count = float(values.size)
    if finite.size == 0 or total_count == 0:
        return {
            "count": 0.0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "p05": None,
            "p95": None,
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
    raw = str(crs_input).strip()
    crs_str = raw.upper().replace(" ", "")

    # `urn:ogc:def:crs:EPSG::4326`, `EPSG::4326`, `EPSG:4326`
    if "EPSG" in crs_str:
        tail = crs_str.rsplit("EPSG", 1)[1].lstrip(":").strip(":")
        if tail.isdigit():
            return int(tail)
        # WKT: the *last* AUTHORITY["EPSG","<code>"] wins (outermost object)
        if "AUTHORITY" in crs_str:
            matches = re.findall(r'AUTHORITY\["EPSG"\s*,\s*"?(\d+)"?\]', crs_str)
            if matches:
                return int(matches[-1])
        if crs_str.isdigit():
            return int(crs_str)
        return None

    if crs_str.isdigit():
        return int(crs_str)

    # PROJ strings: `+proj=longlat +datum=WGS84` is EPSG:4326 by definition.
    if raw.startswith("+"):
        lowered = raw.lower()
        if "+init=epsg:" in lowered:
            code = lowered.split("+init=epsg:", 1)[1].split()[0]
            if code.isdigit():
                return int(code)
        if "proj=longlat" in lowered and "datum=wgs84" in lowered:
            return 4326
        if "proj=longlat" in lowered and "ellps=wgs84" in lowered:
            return 4326
        return None
    return None
