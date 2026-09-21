"""Tests for BaselineStore in geomemory.eval.run_store."""

from __future__ import annotations

import pytest

from geomemory.eval.run_store import BaselineStore, RunStore


class TestBaselineStore:
    def test_set_and_get(self, tmp_path):
        bl = BaselineStore(tmp_path / "bl")
        bl.set("ds1", "20240101T000000Z", str(tmp_path / "runs" / "ds1"), {"b1": {}})
        result = bl.get("ds1")
        assert result is not None
        assert result["timestamp"] == "20240101T000000Z"
        assert result["path"] == str(tmp_path / "runs" / "ds1")
        assert result["metrics"]["b1"] == {}

    def test_get_missing_returns_none(self, tmp_path):
        bl = BaselineStore(tmp_path / "bl2")
        assert bl.get("nope") is None

    def test_list_datasets(self, tmp_path):
        bl = BaselineStore(tmp_path / "bl3")
        bl.set("a", "t1", "/path/a", {"m": {"v": 1}})
        bl.set("b", "t2", "/path/b", {})
        items = bl.list_datasets()
        assert len(items) == 2
        names = {it["dataset"] for it in items}
        assert names == {"a", "b"}

    def test_overwrite_baseline(self, tmp_path):
        bl = BaselineStore(tmp_path / "bl4")
        bl.set("x", "old", "/old", {})
        bl.set("x", "new", "/new", {})
        got = bl.get("x")
        assert got["timestamp"] == "new"
        assert got["path"] == "/new"
