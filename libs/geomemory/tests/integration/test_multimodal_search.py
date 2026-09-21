"""Integration tests for multimodal search fusion via SearchService."""

from __future__ import annotations

import numpy as np

from geomemory.core.models import SearchHit, SearchRequest
from geomemory.index.image_backend import ImageRetrievalBackend
from geomemory.index.image_index import ImageIndex
from geomemory.retrieval.search_service import SearchService


class FakeTextBackend:
    """A minimal text retrieval backend for unit tests."""

    space_id = "text.fake.v1"

    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits

    def search(self, request: SearchRequest) -> list[SearchHit]:
        return self._hits[: request.top_k]


class FakeVisionEmbedder:
    """A minimal cross-modal vision embedder for tests."""

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        return np.array([[1.0, 0.0]], dtype=np.float32)


class TestMultimodalSearch:
    def test_both_fuses_text_and_image_via_rrf(self):
        text_hits = [
            SearchHit(id="seg_1", score=0.9, text="NDVI note", metadata={"modality": "text"}),
            SearchHit(id="seg_2", score=0.7, text="Soil moisture", metadata={"modality": "text"}),
        ]
        index = ImageIndex()
        # _image_backend_ready requires count >= 5
        for i in range(5):
            vec = np.array([float(i), 0.0], dtype=np.float32)
            index.upsert(f"tile_{i}", vec)
        image_backend = ImageRetrievalBackend(index, vision_embedder=FakeVisionEmbedder())
        text_backend = FakeTextBackend(text_hits)
        service = SearchService([text_backend, image_backend])
        result = service.search("ndvi", mode="hybrid", top_k=5, top_n=5, modalities="both")
        ids = {hit.id for hit in result.hits}
        assert "seg_1" in ids or "seg_2" in ids
        assert any("tile_" in hid for hid in ids)

    def test_image_skips_text_backends(self):
        text_hits = [
            SearchHit(id="seg_1", score=0.9, text="NDVI note", metadata={"modality": "text"}),
        ]
        index = ImageIndex()
        for i in range(5):
            vec = np.array([float(i), 0.0], dtype=np.float32)
            index.upsert(f"tile_{i}", vec)
        image_backend = ImageRetrievalBackend(index, vision_embedder=FakeVisionEmbedder())
        text_backend = FakeTextBackend(text_hits)
        service = SearchService([text_backend, image_backend])
        result = service.search("ndvi", mode="dense", top_k=5, top_n=5, modalities="image")
        ids = {hit.id for hit in result.hits}
        assert "seg_1" not in ids
        assert any("tile_" in hid for hid in ids)

    def test_text_skips_image_backends(self):
        text_hits = [
            SearchHit(id="seg_1", score=0.9, text="NDVI note", metadata={"modality": "text"}),
        ]
        index = ImageIndex()
        for i in range(5):
            vec = np.array([float(i), 0.0], dtype=np.float32)
            index.upsert(f"tile_{i}", vec)
        image_backend = ImageRetrievalBackend(index)
        text_backend = FakeTextBackend(text_hits)
        service = SearchService([text_backend, image_backend])
        result = service.search("ndvi", mode="sparse", top_k=5, top_n=5, modalities="text")
        ids = {hit.id for hit in result.hits}
        assert "seg_1" in ids
        assert all("tile_" not in hid for hid in ids)
