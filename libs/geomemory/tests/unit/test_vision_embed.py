"""Unit tests for vision embedding dimension, segment null-safety, and image search abstention."""

from __future__ import annotations

import numpy as np

from geomemory.core.exceptions import ModelNotLoadedError
from geomemory.index.image_index import ImageIndex
from geomemory.index.manifest import load_manifest
from geomemory.ingest.vision_embed import _determine_dimension, _save_image_index


class TestVisionDimension:
    """Test embedding dimension determination in vision_embed."""

    def test_dimension_read_from_image_index_dimension(self, tmp_path):
        """Index dimension() is used when available."""
        index = ImageIndex()
        index.upsert("tile_1", np.zeros(768, dtype=np.float32))
        assert index.dimension() == 768
        assert _determine_dimension(index) == 768

    def test_dimension_read_from_vector_mock(self, tmp_path):
        """Dimension is read from vector method/attribute, NOT from ids."""
        class _MockIndex:
            def ids(self) -> list[str]:
                # IDs are strings and have no .shape attribute
                return ["tile_str_id_1", "tile_str_id_2"]

            def vectors(self, idx: int = 0) -> np.ndarray:
                return np.zeros((1, 512), dtype=np.float32)

            def count(self) -> int:
                return 2

            def save(self, target, manifest):
                pass

        mock_idx = _MockIndex()
        dim = _determine_dimension(mock_idx)
        assert dim == 512

    def test_dimension_read_from_embeddings_dict(self):
        """Dimension is read from _embeddings dict values."""
        class _MockIndex:
            def ids(self) -> list[str]:
                return ["t1"]

            _embeddings = {"t1": np.zeros(768, dtype=np.float32)}

            def count(self) -> int:
                return 1

        assert _determine_dimension(_MockIndex()) == 768

    def test_dimension_fallback_to_768_with_warning(self, caplog):
        """Fallback to 768 with exact warning message when dimension cannot be determined."""
        class _EmptyIndex:
            def ids(self) -> list[str]:
                return []

            def count(self) -> int:
                return 0

        with caplog.at_level("WARNING"):
            dim = _determine_dimension(_EmptyIndex())

        assert dim == 768
        assert "could not determine vision embedding dimension, defaulting to 768" in caplog.text

    def test_save_image_index_writes_768_manifest(self, tmp_path):
        """_save_image_index writes manifest with 768 dimension for OLMoEarth."""
        index = ImageIndex()
        index.upsert("tile_1", np.zeros(768, dtype=np.float32))
        _save_image_index(index, tmp_path, space_id="image.olmoearth-nano-v12.v1")

        manifest = load_manifest(tmp_path / "image")
        assert manifest.dimension == 768
        assert manifest.model_id == "olmoearth-nano-v1.2"


class TestSegmentNullSafety:
    """Test null-safety of segment_ids in workspace ingestion."""

    def test_ingest_duplicate_when_segments_for_revision_returns_none(
        self, temp_workspace, sample_markdown, monkeypatch
    ):
        """Simulate _segments_for_revision returning None; ensure no AttributeError."""
        ws = temp_workspace
        col = ws.create_collection("docs")
        # Ingest document first time
        ws.ingest(sample_markdown, collection_id=col.id)

        # Mock _segments_for_revision to return None on re-ingest (dedup path)
        monkeypatch.setattr(ws, "_segments_for_revision", lambda rev_id: None)

        # Re-ingest the exact same document (triggers dedup check)
        job = ws.ingest(sample_markdown, collection_id=col.id)
        assert job.state == "completed"
        assert job.result is not None
        assert job.result.get("skipped") is True
        assert job.result.get("reason") == "duplicate hash"


class TestImageSearchAbstention:
    """Test image search abstention when vision embedder is unavailable."""

    def test_image_search_abstains_on_model_not_loaded(
        self, temp_workspace, monkeypatch, caplog
    ):
        """Mock vision embedder to raise ModelNotLoadedError; assert [] and warning."""
        ws = temp_workspace

        # Build dummy image index with >= 5 tiles so count check passes
        index = ImageIndex()
        for i in range(6):
            index.upsert(f"tile_{i}", np.zeros(768, dtype=np.float32))

        monkeypatch.setattr(ws, "image_index", lambda: index)

        def _mock_build_vision_embedder(settings):
            raise ModelNotLoadedError("Vision model checkpoint not loaded")

        monkeypatch.setattr(
            "geomemory.embeddings.factory.build_vision_embedder",
            _mock_build_vision_embedder,
        )

        with caplog.at_level("WARNING"):
            hits = ws._image_search(
                "green forest",
                top_k=5,
                collections=None,
                spatial=None,
                temporal=None,
                sensor=None,
                modality_weight=0.7,
            )

        assert hits == []
        assert "Vision embedder unavailable for image search" in caplog.text

    def test_multimodal_search_graceful_degradation(
        self, temp_workspace, sample_markdown, monkeypatch, caplog
    ):
        """Verify text/dense search degrades gracefully when image search abstains."""
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        # Force image search to return empty hits
        monkeypatch.setattr(
            ws,
            "_image_search",
            lambda *args, **kwargs: [],
        )

        # Search with modalities="both"
        result = ws.search("NDVI Sentinel-2", modalities="both", modality_weight=0.8)
        assert result.total_hits > 0
        assert len(result.hits) > 0
        for hit in result.hits:
            assert hit.metadata.get("modality") == "text"
