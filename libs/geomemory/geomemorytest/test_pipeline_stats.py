"""Pipeline statistics tests: schema, types, fresh-vs-ingested behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from geomemory import GeoMemory
from geomemory.eval.pipeline_stats import (
    STATS_FIELDS,
    collect_stats,
    is_valid_stats,
    stats_to_json,
)


class TestPipelineStatsSchema:
    EXPECTED_FIELDS = (
        "files",
        "documents",
        "chunks",
        "embeddings",
        "entities",
        "relations",
        "duration_seconds",
        "storage_bytes",
    )

    def test_stats_fields_constant(self):
        assert STATS_FIELDS == self.EXPECTED_FIELDS

    def test_collect_stats_returns_all_eight_fields(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "stats")
        try:
            stats = ws.pipeline_stats()
            assert set(stats.keys()) == set(self.EXPECTED_FIELDS)
        finally:
            ws.close()

    def test_fresh_workspace_all_zero(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "fresh")
        try:
            stats = ws.pipeline_stats()
            for field in (
                "files",
                "documents",
                "chunks",
                "embeddings",
                "entities",
                "relations",
            ):
                assert stats[field] == 0, field
            assert stats["duration_seconds"] == 0.0
            assert stats["storage_bytes"] >= 0
        finally:
            ws.close()

    def test_stats_reflect_ingested_data(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "ing")
        try:
            coll = ws.create_collection("papers")
            md = tmp_path / "note.md"
            md.write_text("# NDVI\n\nSentinel-2 monitors vegetation.\n", encoding="utf-8")
            ws.ingest(md, collection_id=coll.id)
            stats = ws.pipeline_stats()
            assert stats["files"] == 1
            assert stats["documents"] == 1
            assert stats["chunks"] >= 1
        finally:
            ws.close()

    def test_numeric_json_types(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "json")
        try:
            stats = ws.pipeline_stats()
            text = stats_to_json(stats)
            data = json.loads(text)
            for field in self.EXPECTED_FIELDS:
                assert isinstance(data[field], (int, float)), field
                assert not isinstance(data[field], bool), field
        finally:
            ws.close()

    def test_is_valid_stats_accepts_complete(self):
        stats = {
            "files": 1,
            "documents": 1,
            "chunks": 2,
            "embeddings": 0,
            "entities": 0,
            "relations": 0,
            "duration_seconds": 1.5,
            "storage_bytes": 1024,
        }
        assert is_valid_stats(stats) is True

    def test_is_valid_stats_rejects_partial(self):
        assert is_valid_stats({"files": 1}) is False
        assert is_valid_stats(None) is False
        assert is_valid_stats("not a dict") is False

    def test_is_valid_stats_rejects_bool(self):
        stats = {f: 0 for f in self.EXPECTED_FIELDS}
        stats["files"] = True
        assert is_valid_stats(stats) is False

    def test_duration_seconds_is_float(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "dur")
        try:
            stats = collect_stats(ws.conn, ws.path, duration_seconds=34.2)
            assert stats["duration_seconds"] == pytest.approx(34.2)
            assert isinstance(stats["duration_seconds"], float)
        finally:
            ws.close()

    def test_storage_bytes_increases_with_ingest(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "grow")
        try:
            before = ws.pipeline_stats()["storage_bytes"]
            coll = ws.create_collection("papers")
            md = tmp_path / "big.md"
            md.write_text("# Heading\n\n" + ("body " * 5000), encoding="utf-8")
            ws.ingest(md, collection_id=coll.id)
            after = ws.pipeline_stats()["storage_bytes"]
            assert after >= before
        finally:
            ws.close()


class TestCollectStatsDirectly:
    def test_collect_stats_uses_db_tables(self, tmp_path):
        from geomemory.storage import connect, initialize, migrate, schema_sql

        db = tmp_path / "direct.db"
        conn = connect(db)
        initialize(conn)
        migrate(conn, schema_sql())
        try:
            stats = collect_stats(conn, tmp_path)
            assert stats["files"] == 0
            assert stats["chunks"] == 0
        finally:
            conn.close()

    def test_collect_stats_missing_dir_is_zero_size(self, tmp_path):
        from geomemory.storage import connect, initialize, migrate, schema_sql

        db = tmp_path / "direct2.db"
        conn = connect(db)
        initialize(conn)
        migrate(conn, schema_sql())
        try:
            stats = collect_stats(conn, tmp_path / "nonexistent")
            assert stats["storage_bytes"] == 0
        finally:
            conn.close()