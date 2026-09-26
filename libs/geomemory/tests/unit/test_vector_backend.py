"""Unit tests for VectorBackend (persisted dense vector backend)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from geomemory.core.models import IndexManifest, IndexRecord, SearchRequest
from geomemory.index.vector_backend import VectorBackend


def test_vector_backend_lifecycle(tmp_path: Path) -> None:
    records = [
        IndexRecord(id="r1", text="crop stress", embedding=[1.0, 0.0, 0.0], space_id="text.hash.v1"),
        IndexRecord(id="r2", text="urban heat", embedding=[0.0, 1.0, 0.0], space_id="text.hash.v1"),
        IndexRecord(id="r3", text="water index", embedding=[0.0, 0.0, 1.0], space_id="text.hash.v1"),
    ]
    backend = VectorBackend(records=records)
    assert backend.count() == 3
    assert len(backend.records()) == 3
    embs = backend.embeddings()
    assert embs is not None and embs.shape == (3, 3)

    # Search
    req = SearchRequest(query="crop", query_embedding=[1.0, 0.1, 0.0], top_k=2)
    hits = backend.search(req)
    assert len(hits) == 2
    assert hits[0].id == "r1"
    assert hits[0].dense_score is not None and hits[0].dense_score > 0.9

    # Search with no query embedding
    assert backend.search(SearchRequest(query="crop", top_k=2)) == []

    # Deletion and compaction
    backend.delete(["r2"])
    assert backend.count() == 2
    embs2 = backend.embeddings()
    assert embs2 is not None and embs2.shape == (2, 3)
    assert [r.id for r in backend.records()] == ["r1", "r3"]

    # Deleting non-existent id is no-op
    backend.delete(["non-existent"])
    assert backend.count() == 2
    embs3 = backend.embeddings()
    assert embs3 is not None and embs3.shape == (2, 3)

    # Save and load
    save_dir = tmp_path / "vec_index"
    assert not VectorBackend.exists(save_dir)
    backend.save(save_dir)
    assert VectorBackend.exists(save_dir)

    loaded = VectorBackend.load(save_dir)
    assert loaded.count() == 2
    loaded_embs = loaded.embeddings()
    assert loaded_embs is not None and loaded_embs.shape == (2, 3)
    assert [r.id for r in loaded.records()] == ["r1", "r3"]

    # Delete remaining records
    backend.delete(["r1", "r3"])
    assert backend.count() == 0
    embs4 = backend.embeddings()
    assert embs4 is not None and embs4.shape == (0, 3)
    assert backend.search(req) == []


def test_vector_backend_upsert_with_explicit_embeddings() -> None:
    backend = VectorBackend(space_id="text.custom.v1")
    assert backend.count() == 0
    assert backend.embeddings() is None

    # Empty upsert does nothing
    backend.upsert([])
    assert backend.count() == 0

    recs = [
        IndexRecord(id="a", text="alpha", space_id="text.custom.v1"),
        IndexRecord(id="b", text="beta", space_id="text.custom.v1"),
    ]
    vecs = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    backend.upsert(recs, embeddings=vecs)
    assert backend.count() == 2
    embs5 = backend.embeddings()
    assert embs5 is not None and embs5.shape == (2, 2)

    # Mismatched rows error
    with pytest.raises(ValueError, match="embeddings rows"):
        backend.upsert(recs, embeddings=np.array([[1.0, 2.0]]))

    # Rebuild raises NotImplementedError
    man = IndexManifest(space_id="text.custom.v1", model_id="mod", dimension=2, doc_count=2)
    with pytest.raises(NotImplementedError, match="Use IndexService"):
        backend.rebuild(man)


def test_vector_backend_load_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No persisted index"):
        VectorBackend.load(tmp_path / "missing_dir")
