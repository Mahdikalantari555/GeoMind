"""Unit tests for EmbeddingRepository."""

from __future__ import annotations

from geomemory.core.models import EmbeddingRecord
from geomemory.core.workspace import GeoMemory
from geomemory.storage.repositories.embedding_repo import EmbeddingRepository


def test_embedding_repository_crud(temp_workspace: GeoMemory) -> None:
    repo = EmbeddingRepository(temp_workspace.conn)
    rec1 = EmbeddingRecord(
        target_id="seg-1",
        target_type="segment",
        space_id="text.onnx.v1",
        model_id="minilm",
        dimension=384,
        checksum="1" * 64,
    )
    rec2 = EmbeddingRecord(
        target_id="seg-2",
        target_type="segment",
        space_id="text.onnx.v1",
        model_id="minilm",
        dimension=384,
        checksum="2" * 64,
    )
    rec3 = EmbeddingRecord(
        target_id="seg-1",
        target_type="segment",
        space_id="text.nomic.v1",
        model_id="nomic",
        dimension=768,
        checksum="3" * 64,
    )

    repo.insert(rec1)
    repo.insert(rec2)
    repo.insert(rec3)

    assert repo.count() == 3

    fetched = repo.get("seg-1", "segment", "text.onnx.v1")
    assert fetched is not None
    assert fetched.checksum == "1" * 64

    missing = repo.get("missing", "segment", "text.onnx.v1")
    assert missing is None

    # get_by_space
    onnx_recs = repo.get_by_space("text.onnx.v1")
    assert len(onnx_recs) == 2

    # get_by_target
    seg1_recs = repo.get_by_target("seg-1")
    assert len(seg1_recs) == 2

    # delete single
    assert repo.delete("seg-2", "segment", "text.onnx.v1") is True
    assert repo.delete("seg-2", "segment", "text.onnx.v1") is False
    assert repo.count() == 2

    # delete_by_space
    deleted_count = repo.delete_by_space("text.onnx.v1")
    assert deleted_count == 1
    assert repo.count() == 1
