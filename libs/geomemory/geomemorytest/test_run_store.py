"""Run storage tests: layout, schema, immutability, uniqueness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geomemory.eval.pipeline_stats import STATS_FIELDS
from geomemory.eval.run_store import RunStore, validate_stats


STATS = {
    "files": 1,
    "documents": 1,
    "chunks": 2,
    "embeddings": 0,
    "entities": 0,
    "relations": 0,
    "duration_seconds": 1.5,
    "storage_bytes": 1024,
}


class TestRunStore:
    def test_write_run_creates_layout(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        run_dir = store.write_run(
            dataset="geospatial",
            benchmark="phase1.jsonl",
            stats=STATS,
            rows=[
                {
                    "query": "q1",
                    "retrieved": ["a", "b"],
                    "scores": [0.9, 0.8],
                    "metadata": {"gold_ids": ["a"]},
                    "response": None,
                }
            ],
            timestamp="20260919T120000Z",
            config={"mode": "hybrid"},
            name="phase1",
            metrics={"retrieval": {"recall@1": 1.0}},
        )

        assert run_dir == tmp_path / "runs" / "geospatial" / "20260919T120000Z"
        assert (run_dir / "stats.json").is_file()
        assert (run_dir / "phase1.jsonl.json").is_file()

    def test_stats_json_has_all_eight_numeric_fields(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        run_dir = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        data = json.loads((run_dir / "stats.json").read_text(encoding="utf-8"))
        assert set(data) == set(STATS_FIELDS)
        for field in STATS_FIELDS:
            assert isinstance(data[field], (int, float)), field

    def test_benchmark_json_has_required_keys(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        run_dir = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        data = json.loads((run_dir / "phase1.jsonl.json").read_text(encoding="utf-8"))
        assert set(("name", "config", "metrics", "rows")) <= set(data)
        assert data["name"] == "phase1.jsonl"
        assert data["rows"] == []

    def test_read_run_roundtrip(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        run_dir = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        run = store.read_run("geospatial", "t1")
        assert run["path"] == str(run_dir)
        assert run["stats"] == STATS
        assert run["benchmarks"]["phase1.jsonl"]["rows"] == []

    def test_read_run_missing_raises(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        with pytest.raises(FileNotFoundError):
            store.read_run("geospatial", "missing")

    def test_immutability_second_run_new_dir(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        run_dir = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        original = (run_dir / "stats.json").read_bytes()
        second = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        assert second == tmp_path / "runs" / "geospatial" / "t1-1"
        assert (run_dir / "stats.json").read_bytes() == original
        assert second != run_dir

    def test_same_second_collision_appends_suffix(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        second = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        third = store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        assert second.name == "t1-1"
        assert third.name == "t1-2"

    def test_list_runs(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        store.write_run("temporal", "phase2.jsonl", STATS, [], timestamp="t2")
        runs = store.list_runs()
        assert len(runs) == 2
        assert {r["dataset"] for r in runs} == {"geospatial", "temporal"}

    def test_list_runs_filtered(self, tmp_path: Path):
        store = RunStore(tmp_path / "runs")
        store.write_run("geospatial", "phase1.jsonl", STATS, [], timestamp="t1")
        store.write_run("temporal", "phase2.jsonl", STATS, [], timestamp="t2")
        runs = store.list_runs("geospatial")
        assert [r["dataset"] for r in runs] == ["geospatial"]

    def test_validate_stats_accepts_complete(self):
        assert validate_stats(STATS) is True

    def test_validate_stats_rejects_partial(self):
        assert validate_stats({"files": 1}) is False
        assert validate_stats(None) is False

    def test_validate_stats_rejects_bool(self):
        stats = dict(STATS)
        stats["files"] = True
        assert validate_stats(stats) is False