"""Unit tests for spatial filter predicates and pre-filtering."""

from __future__ import annotations

import sqlite3

from geomemory.core.models import SearchHit, SpatialFilter
from geomemory.core.workspace import GeoMemory
from geomemory.retrieval.spatial_filter import (
    apply_spatial_filter,
    spatial_ids,
)
from geomemory.storage.repositories.spatial_repo import SpatialRepository


def test_apply_spatial_filter_none() -> None:
    hits = [
        SearchHit(id="h1", dense_score=1.0, text="t", locator={}, metadata={})
    ]
    assert apply_spatial_filter(hits, None) == hits


def test_apply_spatial_filter_missing_or_invalid_bbox() -> None:
    hit_no_meta = SearchHit(id="h1", dense_score=1.0, text="t", locator={}, metadata={})
    hit_bad_bbox = SearchHit(id="h2", dense_score=1.0, text="t", locator={}, metadata={"spatial": {"bbox": [1.0, 2.0]}})
    f = SpatialFilter(op="intersects", bbox=(0.0, 0.0, 10.0, 10.0))
    assert apply_spatial_filter([hit_no_meta, hit_bad_bbox], f) == []


def test_apply_spatial_filter_predicates() -> None:
    # hit inside [2, 2, 4, 4]
    hit1 = SearchHit(id="h1", dense_score=1.0, text="t", locator={}, metadata={"spatial": {"bbox": [2.0, 2.0, 4.0, 4.0]}})
    # hit far away [50, 50, 52, 52]
    hit2 = SearchHit(id="h2", dense_score=1.0, text="t", locator={}, metadata={"spatial": {"bbox": [50.0, 50.0, 52.0, 52.0]}})

    # intersects
    f_inter = SpatialFilter(op="intersects", bbox=(1.0, 1.0, 3.0, 3.0))
    res = apply_spatial_filter([hit1, hit2], f_inter)
    assert len(res) == 1 and res[0].id == "h1"

    # within: hit must be within query bbox
    f_within = SpatialFilter(op="within", bbox=(0.0, 0.0, 10.0, 10.0))
    assert len(apply_spatial_filter([hit1, hit2], f_within)) == 1

    # contains: query bbox must be within hit bbox
    f_contains = SpatialFilter(op="contains", bbox=(2.5, 2.5, 3.5, 3.5))
    assert len(apply_spatial_filter([hit1, hit2], f_contains)) == 1

    # distance_lte: center to center distance check
    f_dist = SpatialFilter(op="distance_lte", bbox=(3.0, 3.0, 3.0, 3.0), distance_m=10000.0)
    assert len(apply_spatial_filter([hit1, hit2], f_dist)) == 1

    # invalid op
    f_invalid = SpatialFilter.model_construct(op="invalid_op", bbox=(0.0, 0.0, 10.0, 10.0))
    assert len(apply_spatial_filter([hit1, hit2], f_invalid)) == 0

    f_none_bbox = SpatialFilter.model_construct(op="intersects", bbox=None)
    assert len(apply_spatial_filter([hit1, hit2], f_none_bbox)) == 0


def test_spatial_ids_pre_filter(temp_workspace: GeoMemory) -> None:
    conn = temp_workspace.conn
    repo = SpatialRepository(conn)
    repo.insert("item1", [2.0, 2.0, 4.0, 4.0])
    repo.insert("item2", [50.0, 50.0, 52.0, 52.0])

    # None or missing bbox
    assert spatial_ids(conn, None) == []
    f_no_bbox = SpatialFilter.model_construct(op="intersects", bbox=None)
    assert spatial_ids(conn, f_no_bbox) == []

    # intersects
    f_inter = SpatialFilter(op="intersects", bbox=(1.0, 1.0, 3.0, 3.0))
    assert "item1" in spatial_ids(conn, f_inter)

    # within
    f_within = SpatialFilter(op="within", bbox=(0.0, 0.0, 10.0, 10.0))
    assert "item1" in spatial_ids(conn, f_within)

    # contains
    f_contains = SpatialFilter(op="contains", bbox=(2.5, 2.5, 3.5, 3.5))
    assert "item1" in spatial_ids(conn, f_contains)

    # distance_lte
    f_dist = SpatialFilter(op="distance_lte", bbox=(3.0, 3.0, 3.0, 3.0), distance_m=50000.0)
    assert "item1" in spatial_ids(conn, f_dist)

    # unknown op
    f_unknown = SpatialFilter.model_construct(op="unknown", bbox=(0.0, 0.0, 10.0, 10.0))
    assert spatial_ids(conn, f_unknown) == []
