"""Tests for geomemory.eval.corpus and BenchmarkItem validation."""

from __future__ import annotations

import json
import pytest

from geomemory.eval.benchmark import BenchmarkItem, load_benchmark
from geomemory.eval.corpus import (
    list_corpus_benchmarks,
    load_corpus_registry,
    resolve_corpus_version,
    validate_benchmark_items,
)


class TestValidateBenchmarkItems:
    def test_valid_item(self):
        rows = [{"query": "what is x", "gold_ids": ["g1"]}]
        errors = validate_benchmark_items(rows)
        assert errors == []

    def test_empty_query_rejected(self):
        rows = [{"query": "   ", "gold_ids": []}]
        errors = validate_benchmark_items(rows)
        assert len(errors) == 1
        assert errors[0]["line"] == 1

    def test_missing_gold_ids_ok(self):
        """gold_ids has a default, missing key should pass."""
        rows = [{"query": "q"}]
        errors = validate_benchmark_items(rows)
        assert errors == []

    def test_bad_type_for_gold_ids(self):
        rows = [{"query": "q", "gold_ids": "not-a-list"}]
        errors = validate_benchmark_items(rows)
        assert len(errors) == 1
        assert errors[0]["field"] == "gold_ids"


class TestCorpusRegistry:
    def test_load_corpus_registry(self, tmp_path):
        registry = {
            "phase1": {"version": "v0.1.0", "description": "Retrieval test", "modality": "retrieval"},
        }
        p = tmp_path / "corpus.json"
        p.write_text(json.dumps(registry), encoding="utf-8")
        data = load_corpus_registry(p)
        assert data["phase1"]["version"] == "v0.1.0"

    def test_missing_registry_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_corpus_registry(tmp_path / "nope.json")

    def test_non_dict_registry_raises(self, tmp_path):
        p = tmp_path / "corpus.json"
        p.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ValueError):
            load_corpus_registry(p)


class TestListCorpusBenchmarks:
    def test_empty_dir(self, tmp_path):
        assert list_corpus_benchmarks(tmp_path) == []

    def test_find_jsonl_files(self, tmp_path):
        v1 = tmp_path / "v0.1.0"
        v2 = tmp_path / "v0.2.0"
        v1.mkdir()
        v2.mkdir()
        (v1 / "phase1.jsonl").write_text("", encoding="utf-8")
        (v2 / "qa.jsonl").write_text("", encoding="utf-8")
        results = list_corpus_benchmarks(tmp_path)
        assert len(results) == 2
        versions = {r["version"] for r in results}
        assert versions == {"v0.1.0", "v0.2.0"}


class TestResolveCorpusVersion:
    def test_from_parent_dir(self, tmp_path):
        bench = tmp_path / "v0.2.0" / "phase1.jsonl"
        bench.parent.mkdir(parents=True)
        bench.write_text("", encoding="utf-8")
        ver = resolve_corpus_version(bench)
        assert ver == "v0.2.0"

    def test_from_registry(self, tmp_path):
        corp = tmp_path / "corpus"
        corp.mkdir()
        reg = corp / "corpus.json"
        reg.write_text(json.dumps({"phase1": {"version": "v0.3.0"}}), encoding="utf-8")
        bench = tmp_path / "phase1.jsonl"
        bench.write_text("", encoding="utf-8")
        ver = resolve_corpus_version(bench, corpus_dir=corp)
        assert ver == "v0.3.0"

    def test_no_match_returns_none(self, tmp_path):
        bench = tmp_path / "phase1.jsonl"
        bench.write_text("", encoding="utf-8")
        assert resolve_corpus_version(bench) is None


class TestLoadBenchmarkWithVersion:
    def test_version_attached(self, tmp_path):
        corp = tmp_path / "corpus"
        corp.mkdir()
        reg = corp / "corpus.json"
        reg.write_text(json.dumps({"phase1": {"version": "v0.5.0"}}), encoding="utf-8")
        bench = corp / "phase1.jsonl"
        bench.write_text(
            json.dumps({"query": "q1", "gold_ids": ["g1"]}),
            encoding="utf-8",
        )
        loaded = load_benchmark(bench, corpus_dir=corp)
        assert loaded.metadata.get("corpus_version") == "v0.5.0"

    def test_validation_error_line_context(self, tmp_path):
        bad = tmp_path / "bad.jsonl"
        bad.write_text(
            json.dumps({"query": "", "gold_ids": []}) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="line"):
            load_benchmark(bad)
