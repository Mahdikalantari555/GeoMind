"""Unit tests for LanceBackend with real LanceDB."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from geomemory.core.models import IndexRecord, SearchRequest
from geomemory.index.lance_backend import LanceBackend, _safe_space, _table_path


def test_safe_space_and_table_path(tmp_path: Path) -> None:
    assert _safe_space(None) == "text.hash.v1"
    assert _safe_space("custom.space") == "custom.space"
    p = _table_path(tmp_path, "space1")
    assert p == tmp_path / "lancedb" / "space1.lance"


def test_lance_backend_lifecycle(tmp_path: Path) -> None:
    records = [
        IndexRecord(id="r1", text="crop stress with NDVI", embedding=[1.0, 0.0, 0.0], space_id="text.lance.v1"),
        IndexRecord(id="r2", text="urban heat island", embedding=[0.0, 1.0, 0.0], space_id="text.lance.v1"),
        IndexRecord(id="r3", text="water body detection", embedding=[0.0, 0.0, 1.0], space_id="text.lance.v1"),
    ]
    backend = LanceBackend(space_id="text.lance.v1")
    backend._base_dir = tmp_path

    # Upsert with per-record embeddings
    backend.upsert(records)
    assert backend.count() == 3
    assert len(backend.records()) == 3
    embs = backend.embeddings()
    assert embs is not None and embs.shape == (3, 3)

    # Search with embedding
    req = SearchRequest(query="crop", query_embedding=[0.9, 0.1, 0.0], top_k=2)
    hits = backend.search(req)
    assert len(hits) == 2
    assert hits[0].id == "r1"
    assert hits[0].dense_score is not None

    # Search with None query_embedding returns empty
    assert backend.search(SearchRequest(query="crop", top_k=2)) == []

    # Deletion
    backend.delete(["r2"])
    assert backend.count() == 2
    # Deleting non-existent ID
    backend.delete(["r999"])
    assert backend.count() == 2

    # Save and exists
    save_dir = tmp_path / "indexes" / "text.lance.v1"
    assert not LanceBackend.exists(save_dir)
    backend.save(save_dir)
    assert LanceBackend.exists(save_dir)

    # Load from flat saved files
    loaded = LanceBackend.load(save_dir)
    assert loaded.count() == 2
    assert loaded.space_id == "text.lance.v1"

    # Delete remaining
    backend.delete(["r1", "r3"])
    assert backend.count() == 0


def test_lance_backend_upsert_explicit_embeddings(tmp_path: Path) -> None:
    backend = LanceBackend(space_id="text.lance.v2")
    backend._base_dir = tmp_path

    # Empty upsert
    backend.upsert([])
    assert backend.count() == 0

    recs = [
        IndexRecord(id="a", text="apple", space_id="text.lance.v2"),
        IndexRecord(id="b", text="banana", space_id="text.lance.v2"),
    ]
    vecs = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    # Row mismatch raises ValueError
    with pytest.raises(ValueError, match="embeddings rows"):
        backend.upsert(recs, embeddings=np.array([[1.0, 0.0]]))

    backend.upsert(recs, embeddings=vecs)
    assert backend.count() == 2
    embs2 = backend.embeddings()
    assert embs2 is not None and embs2.shape == (2, 2)

    # Upsert with no embeddings in record falls back to None
    rec_no_emb = [IndexRecord(id="c", text="no embedding", space_id="text.lance.v2")]
    backend2 = LanceBackend(space_id="text.noemb.v1")
    backend2.upsert(rec_no_emb)
    assert backend2.embeddings() is None


def test_lance_backend_direct_table_save_and_load(tmp_path: Path) -> None:
    lance_table_dir = tmp_path / "indexes" / "text.direct.v1"
    backend = LanceBackend(space_id="text.direct.v1")
    backend.upsert(
        [IndexRecord(id="d1", text="direct doc", embedding=[0.5, 0.5])],
        embeddings=np.array([[0.5, 0.5]], dtype=np.float32),
    )
    backend.save(lance_table_dir)
    assert LanceBackend.exists(lance_table_dir)
    assert LanceBackend.exists(tmp_path / "indexes")

    # Load from table dir (flat fallback)
    loaded = LanceBackend.load(lance_table_dir, space_id="text.direct.v1")
    assert loaded.count() == 1
    assert loaded.records()[0].id == "d1"

    # Remove records.json to exercise loading directly from LanceDB table
    (lance_table_dir / "records.json").unlink()
    loaded_lance = LanceBackend.load(lance_table_dir, space_id="text.direct.v1")
    assert loaded_lance.count() == 1
    assert loaded_lance.records()[0].id == "d1"
    assert loaded_lance.embeddings() is not None

    # Load from missing dir raises FileNotFoundError
    with pytest.raises(FileNotFoundError, match="No persisted Lance index"):
        LanceBackend.load(tmp_path / "nonexistent")


def test_lance_backend_fallback_search(tmp_path: Path) -> None:
    backend = LanceBackend(space_id="text.fallback.v1")
    backend.upsert(
        [
            IndexRecord(id="f1", text="first", embedding=[1.0, 0.0]),
            IndexRecord(id="f2", text="second", embedding=[0.0, 1.0]),
        ]
    )
    # Mock _ensure_table returning None to test fallback to _cosine_search
    with patch.object(backend, "_ensure_table", return_value=None):
        req = SearchRequest(query="test", query_embedding=[1.0, 0.0], top_k=1)
        hits = backend.search(req)
        assert len(hits) == 1
        assert hits[0].id == "f1"

    # If table.search raises, fallback to _cosine_search is triggered
    mock_table = MagicMock()
    mock_table.search.side_effect = RuntimeError("Lance internal error")
    with patch.object(backend, "_ensure_table", return_value=mock_table):
        hits = backend.search(req)
        assert len(hits) == 1
        assert hits[0].id == "f1"
