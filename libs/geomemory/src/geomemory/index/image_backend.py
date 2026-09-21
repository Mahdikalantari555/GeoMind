"""Image retrieval adapter for vision-embedded raster tiles."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest
from geomemory.index.image_index import ImageIndex

logger = logging.getLogger(__name__)


class ImageRetrievalBackend:
    """Adapt an :class:`ImageIndex` to the retrieval backend protocol.

    OLMoEarth's production vision encoder is image-only. Text queries therefore
    use ``embed_texts`` when a cross-modal encoder is available and otherwise
    abstain (return empty hits) instead of searching with a zero vector.
    """

    space_id = "image.olmoearth-nano-v12.v1"

    def __init__(
        self,
        image_index: ImageIndex,
        vision_embedder: Any | None = None,
        *,
        space_id: str | None = None,
    ) -> None:
        self.image_index = image_index
        self.vision_embedder = vision_embedder
        if space_id is not None:
            self.space_id = space_id

    def upsert(self, records: list[IndexRecord]) -> None:
        """Insert image records whose ``embedding`` field contains a vector."""
        for record in records:
            if record.embedding is not None:
                self.image_index.upsert(record.id, np.asarray(record.embedding))

    def search(self, request: SearchRequest) -> list[SearchHit]:
        """Return ranked image hits with image modality metadata."""
        if self.image_index.count() == 0:
            return []

        query_vector = self._query_vector(request)
        if query_vector is None:
            return []

        if np.all(query_vector == 0):
            logger.warning("Zero-vector query detected; abstaining from image search")
            return []

        dimension = self.image_index.dimension()
        if dimension is not None and np.asarray(query_vector).shape[-1] != dimension:
            return []

        hits: list[SearchHit] = []
        for result in self.image_index.search(query_vector, top_k=request.top_k):
            target_id = str(result["target_id"])
            score = float(result["score"])
            hits.append(
                SearchHit(
                    id=target_id,
                    dense_score=score,
                    text="",
                    locator={"target_id": target_id, "scene_id": target_id},
                    metadata={
                        "modality": "image",
                        "target_type": "raster_tile",
                        "space_id": self.space_id,
                    },
                )
            )
        return hits[: request.top_k]

    def delete(self, ids: list[str]) -> None:
        """Remove indexed image targets by id."""
        for target_id in ids:
            self.image_index.delete(target_id)

    def rebuild(self, manifest: IndexManifest) -> None:
        """ImageIndex is populated by the ingestion pipeline; rebuilding is a no-op."""
        del manifest

    def count(self) -> int:
        """Return the number of indexed image targets."""
        return self.image_index.count()

    def _query_vector(self, request: SearchRequest) -> np.ndarray | None:
        if request.query_embedding is not None:
            vec = np.asarray(request.query_embedding, dtype=np.float32)
            if np.all(vec == 0):
                logger.warning("Query vector is all zeros; abstaining from image search")
                return None
            return vec

        embed_texts = getattr(self.vision_embedder, "embed_texts", None)
        if embed_texts is not None:
            try:
                embedded = embed_texts([request.query])
            except Exception as exc:
                logger.warning(
                    "Vision embedder text encoding failed for query %r: %s; abstaining from image search",
                    request.query,
                    exc,
                )
                return None

            if embedded is not None:
                vectors = np.asarray(embedded, dtype=np.float32)
                if vectors.ndim == 2 and vectors.shape[0]:
                    v2 = np.asarray(vectors[0], dtype=np.float32)
                    if np.all(v2 == 0):
                        logger.warning("Query vector is all zeros; abstaining from image search")
                        return None
                    return v2
                if vectors.ndim == 1:
                    v1 = np.asarray(vectors, dtype=np.float32)
                    if np.all(v1 == 0):
                        logger.warning("Query vector is all zeros; abstaining from image search")
                        return None
                    return v1

        logger.warning(
            "Image retrieval backend cannot embed query %r without cross-modal text encoder; abstaining from image search",
            request.query,
        )
        return None
