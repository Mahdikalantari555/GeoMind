"""Counterexamples from the fourth QA pass: domain models and geodesy.

Synthetic geometry and arrays only.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from geospatial_core.gis import (
    geodesic_polygon_area_m2,
    parse_epsg,
    polygon_area_deg2,
    reclassify_array,
    zonal_statistics,
)
from pydantic import ValidationError

from geodomain.identity import EntityRef
from geodomain.labels import LabelDefinition, LabelRegistry, LabelSet
from geodomain.observation import Observation, ObservationRef
from geodomain.temporal import TemporalKind

BOX = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
NORTH_BOX = {"type": "Polygon", "coordinates": [[[0, 60], [1, 60], [1, 61], [0, 61], [0, 60]]]}


# ── geodesic area ─────────────────────────────────────────────────────────


def test_geodesic_area_uses_absolute_latitude():
    """A 1°×1° cell at 60°N must be about cos(60°)=0.5 of an equatorial cell."""
    equator = geodesic_polygon_area_m2(BOX)
    north = geodesic_polygon_area_m2(NORTH_BOX)
    ratio = north / equator
    assert 0.45 < ratio < 0.55, f"got {ratio:.3f} — the sin(lat) term is applied in the wrong frame"
    # Independent cross-check: spherical rectangle area.
    r = 6371008.8
    expected = (r**2) * math.radians(1) * (math.sin(math.radians(61)) - math.sin(math.radians(60)))
    assert north == pytest.approx(expected, rel=0.02)


def test_geodesic_area_handles_dateline_crossing():
    """A 0.2°×0.2° box crossing the antimeridian is small, not half the globe."""
    dl = {
        "type": "Polygon",
        "coordinates": [[[179.9, -0.1], [-179.9, -0.1], [-179.9, 0.1], [179.9, 0.1], [179.9, -0.1]]],
    }
    area_km2 = geodesic_polygon_area_m2(dl) / 1e6
    expected = 0.2 * 0.2 * 111.32 * 110.57
    assert area_km2 == pytest.approx(expected, rel=0.05), f"got {area_km2:.1f} km²"


def test_geodesic_area_rejects_a_self_intersecting_ring():
    bow = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    with pytest.raises(ValueError):
        geodesic_polygon_area_m2(bow)


def test_planar_area_flags_a_hole_bigger_than_its_shell():
    bad = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],
            [[-5, -5], [-5, 6], [6, 6], [6, -5], [-5, -5]],
        ],
    }
    with pytest.raises(ValueError):
        polygon_area_deg2(bad)


def test_polygon_area_rejects_unknown_geometry_types():
    """A typo'd/non-areal geometry used to return a confident 0.0."""
    for geom in ({"type": "Point", "coordinates": [0, 0]}, {"type": "Polygonn", "coordinates": []}):
        with pytest.raises(ValueError):
            polygon_area_deg2(geom)


# ── CRS parsing ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "epsg: 4326",
        "EPSG : 4326",
        "urn:ogc:def:crs:EPSG::4326",
        "EPSG::4326",
        "epsg:4326 ",
    ],
)
def test_common_crs_spellings_resolve(text):
    assert parse_epsg(text) == 4326


def test_wkt_wrapped_epsg_is_resolved():
    wkt = 'PROJCS["WGS 84 / UTM zone 23S",GEOGCS["WGS 84",AUTHORITY["EPSG","4326"]],AUTHORITY["EPSG","32723"]]'
    assert parse_epsg(wkt) == 32723


def test_proj_string_is_not_silently_unparsed():
    """`+proj=longlat +datum=WGS84` means 4326; returning None drops the CRS."""
    assert parse_epsg("+proj=longlat +datum=WGS84 +no_defs") == 4326


# ── zonal statistics ──────────────────────────────────────────────────────


def test_zonal_statistics_ignores_the_canonical_nodata_sentinel():
    """-9999 is the project's nodata fill; it must not reach the mean."""
    stats = zonal_statistics(np.array([[1.0, -9999.0]]))
    assert stats["mean"] == 1.0
    assert stats["minimum"] == 1.0 if "minimum" in stats else True
    assert stats["count"] == 1.0
    assert stats["nodata_share"] == 0.5


def test_zonal_statistics_reports_an_empty_zone_honestly():
    stats = zonal_statistics(np.array([[-9999.0, -9999.0]]))
    assert stats["count"] == 0.0
    assert stats["mean"] is None or math.isnan(stats["mean"])


# ── reclassification ──────────────────────────────────────────────────────


def test_reclassify_refuses_a_value_that_collides_with_nodata():
    with pytest.raises(ValueError):
        reclassify_array(np.array([[1.0]]), [{"min": 0, "max": 2, "out": -9999}])


def test_reclassify_refuses_a_fractional_class_value():
    with pytest.raises(ValueError):
        reclassify_array(np.array([[1.0]]), [{"min": 0, "max": 2, "out": 2.7}])


def test_reclassify_rejects_gap_free_but_inverted_rule_lists():
    with pytest.raises(ValueError):
        reclassify_array(np.array([[1.0]]), [{"min": 5, "max": 2, "out": 1}])


# ── labels ────────────────────────────────────────────────────────────────


def test_duplicate_class_ids_are_rejected():
    with pytest.raises(ValidationError):
        LabelSet(
            name="dup",
            labels=[
                LabelDefinition(name="a", class_id=1),
                LabelDefinition(name="b", class_id=1),
            ],
        )


def test_duplicate_class_names_are_rejected():
    with pytest.raises(ValidationError):
        LabelSet(
            name="dup",
            labels=[
                LabelDefinition(name="a", class_id=1),
                LabelDefinition(name="a", class_id=2),
            ],
        )


def test_boolean_is_not_a_class_id():
    assert LabelRegistry.validate_label(True) is False
    assert LabelRegistry.validate_label(0) is True


# ── observations / identity ───────────────────────────────────────────────


def test_observation_needs_a_usable_id():
    with pytest.raises(ValidationError):
        ObservationRef(observation_id="")
    with pytest.raises(ValidationError):
        Observation(id="", subject_id="s", metric="ndvi", value=1.0)


def test_observation_rejects_non_finite_values():
    with pytest.raises(ValidationError):
        Observation(subject_id="s", metric="ndvi", value=float("nan"))
    with pytest.raises(ValidationError):
        Observation(subject_id="s", metric="ndvi", value=float("inf"))


def test_entity_ref_roundtrip_rejects_separators_inside_each_part():
    ref = EntityRef.from_uri("geo:farm/field-1")
    assert ref.to_uri() == "geo:farm/field-1"
    with pytest.raises(ValidationError):
        EntityRef(type="farm/x", id="1")
    with pytest.raises(ValueError):
        EntityRef.from_uri("geo:farm/")
    with pytest.raises(ValueError):
        EntityRef.from_uri("geo:/farm")


def test_temporal_kind_members_are_screaming_case():
    assert TemporalKind.PUBLISHED_AT.value == "published_at"
    assert TemporalKind.PUBLISHED_AT.name == "PUBLISHED_AT"
    # The lower-case `PUBLISHED_at` member leaked into `TemporalKind.__members__`.
    assert set(TemporalKind.__members__) == {
        "ACQUIRED_AT",
        "OBSERVED_AT",
        "PUBLISHED_AT",
        "INGESTED_AT",
        "CREATED_AT",
        "UTCNOWISO_DUMMY",
    } - {"UTCNOWISO_DUMMY"}
