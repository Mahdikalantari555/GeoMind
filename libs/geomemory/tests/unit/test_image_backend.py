"""Unit tests for ImageRetrievalBackend."""

from __future__ import annotations

import numpy as np
import pytest

from geomemory.core.models import SearchHit, SearchRequest
from geomemory.index.image_backend import ImageRetrievalBackend
from geomemory.index.image_index import ImageIndex


class TestImageRetrievalBackend:
    def test_search_returns_empty_for_empty_index(self):
        index = ImageIndex()
        backend = ImageRetrievalBackend(index)
        request = SearchRequest(query="ndvi", top_k=5)
        result = backend.search(request)
        assert result == []

    def test_search_returns_hits_with_modality_image(self):
        index = ImageIndex()
        index.upsert("tile_a", np.array([1.0, 0.0, 0.0], dtype=np.float32))
        index.upsert("tile_b", np.array([0.0, 1.0, 0.0], dtype=np.float32))
        backend = ImageRetrievalBackend(index)
        request = SearchRequest(query="green", top_k=5)
        result = backend.search(request)
        assert len(result) == 2
        for hit in result:
            assert hit.metadata.get("modality") == "image"
        # First hit should be tile_a (cosine similarity 1.0 with [1,0,0])
        assert result[0].id == "tile_a"

    def test_search_respects_top_k(self):
        index = ImageIndex()
        vectors = [np.array([float(i), 0.0, 0.0], dtype=np.float32) for i in range(5)]
        for i, vec in enumerate(vectors):
            index.upsert(f"tile_{i}", vec)
        backend = ImageRetrievalBackend(index)
        # Query vector matching tile_4 best
        request = SearchRequest(query="x", top_k=2)
        result = backend.search(request)
        assert len(result) <= 2
        for hit in result:
            assert hit.metadata.get("modality") == "image"
