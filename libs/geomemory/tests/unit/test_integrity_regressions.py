"""Regression tests for geomemory integrity fixes (M-050…M-059)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from geomemory import GeoMemory
from geomemory.core.events import DomainEvent, EventBus
from geomemory.core.exceptions import DatabaseError
from geomemory.core.models import SearchHit
from geomemory.qa.citation import map_citations
from geomemory.retrieval.fusion import normalized_relevance
from geomemory.retrieval.temporal_filter import time_in_range
from geomemory.services.index_service import IndexService
from geomemory.storage import connect, schema_sql, write_with_retry
from geomemory.storage.migrations import MIGRATIONS as REAL_MIGRATIONS
from geomemory.storage.migrations import (
    Migration,
    current_version,
    migrate,
)
from geomemory.storage.repositories.asset_repo import AssetRepository

UNIQUE_TOKEN = "zzqxtyruniqueassettoken"


def _ingest(ws: GeoMemory, text: str, filename: str = "doc.md") -> None:
    col = ws.create_collection("docs")
    doc = Path(ws.path) / filename
    doc.write_text(text, encoding="utf-8")
    ws.ingest(str(doc), collection_id=col.id)


def test_deleted_asset_not_searchable(tmp_path: Path) -> None:
    ws = GeoMemory.create(tmp_path / "ws")
    _ingest(ws, f"Sugarcane NDVI threshold {UNIQUE_TOKEN} is 0.42.")
    assert any(UNIQUE_TOKEN in hit.text for hit in ws.search(UNIQUE_TOKEN).hits)

    asset = ws.list_assets()[0]
    assert AssetRepository(ws.conn).soft_delete(asset.id)
    assert not any(UNIQUE_TOKEN in hit.text for hit in ws.search(UNIQUE_TOKEN).hits)
    # The source-level FTS path also excludes the deleted segment.
    assert ws._fts_match(UNIQUE_TOKEN, 10, None) == []


def test_migration_failure_leaves_no_ddl_or_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failing = [
        *REAL_MIGRATIONS,
        Migration(
            version=999,
            description="failure injection",
            sql="CREATE TABLE half_baked (v INTEGER); THIS IS NOT VALID SQL;",
        ),
    ]
    monkeypatch.setattr("geomemory.storage.migrations.MIGRATIONS", failing)
    conn = connect(tmp_path / "fail.db")
    with pytest.raises(DatabaseError, match="999"):
        migrate(conn, schema_sql())
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert "half_baked" not in names
    assert current_version(conn) != 999
    assert not conn.in_transaction


def test_write_retry_rolls_back_partial_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "retry.db")
    conn.execute("CREATE TABLE t (v INTEGER)")
    conn.commit()

    def _partial_then_busy() -> None:
        conn.execute("INSERT INTO t VALUES (1)")
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("time.sleep", lambda _s: None)
    with pytest.raises(DatabaseError):
        write_with_retry(conn, _partial_then_busy, attempts=2)
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_event_subscriber_error_is_isolated() -> None:
    bus = EventBus()
    seen: list[str] = []

    def bad(_event: DomainEvent) -> None:
        raise RuntimeError("subscriber exploded")

    bus.subscribe("asset_created", bad)
    bus.subscribe("asset_created", lambda event: seen.append(event.entity_id))
    bus.emit(DomainEvent(event_type="asset_created", entity_id="asset-1"))
    assert seen == ["asset-1"]


def test_temporal_filter_mixed_timestamp_representations() -> None:
    assert time_in_range("2024-01-01T03:00:00+03:00", "2024-01-01T00:00:00Z", None)
    assert time_in_range("2024-01-01", None, "2024-01-01T23:59:59Z")
    assert not time_in_range("2024-01-02T00:00:00Z", None, "2024-01-01T23:59:59Z")
    assert not time_in_range(1234, None, None)  # type: ignore[arg-type]


def test_citation_target_type_is_preserved() -> None:
    hit = SearchHit(
        id="tile-1",
        text="raster",
        metadata={"target_type": "raster_tile", "target_id": "tile-1"},
    )
    citation = map_citations("ans-1", "See [1]", [hit])[0]
    assert citation.target_type == "raster_tile"
    assert citation.target_id == "tile-1"


def test_normalized_relevance_uses_similarity_not_rrf() -> None:
    rrf_hit = SearchHit(id="a", score=1 / 61)
    dense_hit = SearchHit(id="b", dense_score=0.9)
    assert normalized_relevance(rrf_hit) == pytest.approx(1.0)
    assert normalized_relevance(dense_hit) == pytest.approx(0.9)


def test_configured_objects_dir_is_used(tmp_path: Path) -> None:
    ws = GeoMemory.create(tmp_path / "ws")
    ws.update_settings(objects_dir="custom-objects")
    ws.close()
    reopened = GeoMemory.open(tmp_path / "ws")
    digest = reopened.objects.put_bytes(b"payload")
    assert reopened.objects.get_path(digest).is_relative_to(
        tmp_path / "ws" / "custom-objects"
    )
    assert reopened.stats()["objects_bytes"] > 0


def test_index_service_rejects_non_text_space(tmp_path: Path) -> None:
    from geomemory.core.models import WorkspaceSettings

    service = IndexService(
        connect(tmp_path / "db.sqlite"), tmp_path / "indexes", settings=WorkspaceSettings(name="w")
    )
    # Build is created from a bare path with no schema; the modality guard
    # fires before any DB access.
    with pytest.raises(ValueError, match="non-text space"):
        service.build("image.olmoearth.v1")
    with pytest.raises(ValueError, match="non-text space"):
        service.search("x", space_id="image.olmoearth.v1")


def test_retrieval_run_results_are_bounded(tmp_path: Path) -> None:
    ws = GeoMemory.create(tmp_path / "ws")
    _ingest(ws, f"{UNIQUE_TOKEN} threshold 0.42")
    result = ws.search(UNIQUE_TOKEN)
    row = ws.conn.execute(
        "SELECT results FROM retrieval_run WHERE id = ?", (result.retrieval_run_id,)
    ).fetchone()
    logged = json.loads(row["results"])
    assert len(logged) <= ws.MAX_LOGGED_RESULTS
    assert all(len(item.get("text", "")) <= ws.MAX_LOGGED_TEXT_CHARS + 1 for item in logged)
