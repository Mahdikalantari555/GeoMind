"""Hybrid search capability of the workspace facade."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Literal

from geomemory.core.models import (
    QueryPlan,
    RetrievalRun,
    SearchFilters,
    SearchHit,
    SearchRequest,
    SearchResult,
    SpatialFilter,
    TemporalFilter,
)
from geomemory.core.workspace_assets import AssetsMixin
from geomemory.core.workspace_ingest import _FTS_TERM_RE
from geomemory.core.workspace_shared import (
    _load_json,
    logger,
)
from geomemory.index.image_backend import ImageRetrievalBackend
from geomemory.retrieval.fusion import rrf_fuse
from geomemory.retrieval.search_service import SearchService, apply_hit_filters
from geomemory.storage.repositories.segment_repo import SegmentRepository


class SearchMixin(AssetsMixin):
    # ── Search (sparse FTS5 + dense numpy fallback) ─────────────────────────

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 20,
        top_n: int = 5,
        collections: list[str] | None = None,
        spatial: SpatialFilter | None = None,
        temporal: TemporalFilter | None = None,
        sensor: list[str] | None = None,
        expand_relations: bool = False,
        modalities: Literal["text", "image", "both"] | None = None,
        modality_weight: float = 0.7,
    ) -> SearchResult:
        """Execute text, image, or fused multimodal retrieval."""
        if not 0.0 <= modality_weight <= 1.0:
            raise ValueError("modality_weight must be between 0 and 1")

        start = time.perf_counter()
        query = (query or "").strip()
        effective_modalities = modalities or "text"
        filters = SearchFilters(
            collections=collections, sensors=sensor, spatial=spatial, temporal=temporal
        )
        plan = QueryPlan(
            intent="search",
            mode=mode,
            spaces=(["text.sparse", "text.dense"] if effective_modalities != "image" else [])
            + (["image.olmoearth-nano-v12.v1"] if effective_modalities != "text" else []),
            top_k=top_k,
            top_n=top_n,
            filters=filters,
            modalities=effective_modalities,
            modality_weight=modality_weight,
        )

        sparse_hits: list[SearchHit] = []
        dense_hits: list[SearchHit] = []
        if effective_modalities in ("text", "both"):
            sparse_hits = self._fts_search(query, top_k=top_k, collections=collections)
            if mode in ("dense", "hybrid") or effective_modalities == "both" or not sparse_hits:
                dense_hits = self._dense_search(query, top_k=top_k, collections=collections)
            for hit in [*sparse_hits, *dense_hits]:
                hit.metadata.setdefault("modality", "text")

        image_hits: list[SearchHit] = []
        if effective_modalities in ("image", "both"):
            image_hits = self._image_search(
                query,
                top_k=top_k,
                collections=collections,
                spatial=spatial,
                temporal=temporal,
                sensor=sensor,
                modality_weight=modality_weight,
            )

        if effective_modalities == "image":
            fused = image_hits[:top_n]
        elif effective_modalities == "both":
            fused = rrf_fuse(
                [sparse_hits, dense_hits, image_hits],
                top_n=top_n,
                weights=[1.0, 1.0, modality_weight],
            )
        elif mode == "dense":
            fused = dense_hits[:top_n]
        elif mode == "sparse":
            fused = sparse_hits[:top_n] if sparse_hits else dense_hits[:top_n]
        else:
            fused = rrf_fuse([sparse_hits, dense_hits], top_n=top_n)

        # Candidate memory is a text tier and must not enter image-only retrieval.
        if effective_modalities != "image":
            candidate_hits = self._candidate_search(query, top_k=top_k)
            if candidate_hits:
                for hit in candidate_hits:
                    hit.metadata.setdefault("modality", "text")
                fused = self._merge_candidate_hits(fused, candidate_hits, top_n=top_n)
        fused = apply_hit_filters(fused, spatial=spatial, temporal=temporal, sensors=sensor)

        # Expand relations: append supplementary context from related entities.
        if expand_relations and effective_modalities != "image":
            expanded = self._expand_relation_context(list(fused))
            if expanded:
                fused = list(fused) + expanded

        latency_ms = int((time.perf_counter() - start) * 1000)
        run = RetrievalRun(
            query=query,
            query_plan=plan.model_dump(),
            filters=filters.model_dump(),
            config={
                "mode": mode,
                "top_k": top_k,
                "top_n": top_n,
                "fusion": "rrf",
                "modalities": effective_modalities,
                "modality_weight": modality_weight,
            },
            latency_ms=latency_ms,
        )
        self._save_retrieval_run(run, [h.model_dump() for h in fused])

        result = SearchResult(
            query=query,
            query_plan=plan,
            hits=fused,
            total_hits=len(fused),
            latency_ms=latency_ms,
            retrieval_run_id=run.id,
        )
        return result

    def _image_search(
        self,
        query: str,
        *,
        top_k: int,
        collections: list[str] | None,
        spatial: SpatialFilter | None,
        temporal: TemporalFilter | None,
        sensor: list[str] | None,
        modality_weight: float,
    ) -> list[SearchHit]:
        """Retrieve and enrich image hits when the vision index is populated."""
        index = self.image_index()
        if index.count() < 5:
            return []

        from geomemory.embeddings.factory import build_vision_embedder

        try:
            embedder = build_vision_embedder(self.settings)
        except Exception as exc:
            logger.warning("Vision embedder unavailable for image search: %s; returning empty hits", exc)
            return []

        space_id = str(getattr(index, "space_id", "image.olmoearth-nano-v12.v1"))
        backend = ImageRetrievalBackend(index, embedder, space_id=space_id)
        request = SearchRequest(
            query=query,
            mode="hybrid",
            top_k=top_k,
            top_n=top_k,
            modalities="image",
            modality_weight=modality_weight,
        )
        try:
            raw_hits = backend.search(request)
        except Exception as exc:
            logger.warning("Image retrieval backend search failed: %s; returning empty hits", exc)
            return []

        hits = self._enrich_image_hits(raw_hits)
        if collections:
            hits = [
                hit
                for hit in hits
                if str(hit.metadata.get("collection_id", "")) in collections
            ]
        return apply_hit_filters(hits, spatial=spatial, temporal=temporal, sensors=sensor)

    def _enrich_image_hits(self, hits: list[SearchHit]) -> list[SearchHit]:
        """Attach raster provenance needed by filters, citations, and the UI."""
        sql = (
            "SELECT rt.id AS target_id, rt.scene_id, rt.preview_path, "
            "rt.metadata AS tile_metadata, rs.revision_id, rs.sensor, "
            "rs.bbox AS scene_bbox, rs.acquired_at, rs.metadata AS scene_metadata, "
            "ar.asset_id, ar.ingested_at, a.collection_id, a.title, "
            "a.metadata AS asset_metadata "
            "FROM raster_tile rt "
            "JOIN raster_scene rs ON rs.id = rt.scene_id "
            "JOIN asset_revision ar ON ar.id = rs.revision_id "
            "JOIN asset a ON a.id = ar.asset_id "
            "WHERE rt.id = ?"
        )
        for hit in hits:
            row = self.conn.execute(sql, (hit.id,)).fetchone()
            metadata = dict(hit.metadata)
            locator = dict(hit.locator)
            metadata["modality"] = "image"
            metadata["target_type"] = "raster_tile"
            metadata["target_id"] = hit.id
            locator.setdefault("target_id", hit.id)
            locator["modality"] = "image"
            locator["target_type"] = "raster_tile"
            if row is None:
                hit.metadata = metadata
                hit.locator = locator
                continue

            tile_metadata = _load_json(row["tile_metadata"])
            scene_metadata = _load_json(row["scene_metadata"])
            asset_metadata = _load_json(row["asset_metadata"])
            bbox = _load_json(row["scene_bbox"])
            scene_id = str(row["scene_id"])
            revision_id = str(row["revision_id"])
            asset_id = str(row["asset_id"])
            collection_id = str(row["collection_id"])
            acquired_at = row["acquired_at"]
            ingested_at = row["ingested_at"]
            sensor_value = row["sensor"]

            metadata.update(tile_metadata)
            metadata.update(scene_metadata)
            metadata.update(asset_metadata)
            metadata.update(
                {
                    "scene_id": scene_id,
                    "revision_id": revision_id,
                    "asset_id": asset_id,
                    "collection_id": collection_id,
                    "acquired_at": acquired_at,
                    "ingested_at": ingested_at,
                    "title": row["title"],
                    "preview_path": row["preview_path"],
                }
            )
            if sensor_value:
                metadata["sensor"] = sensor_value
            spatial_metadata: dict[str, Any] = {}
            if isinstance(bbox, list) and len(bbox) == 4:
                spatial_metadata["bbox"] = [float(value) for value in bbox]
            if acquired_at:
                spatial_metadata["acquired_at"] = str(acquired_at)
            if sensor_value:
                spatial_metadata["sensor"] = str(sensor_value)
            if spatial_metadata:
                metadata["spatial"] = spatial_metadata

            observation = self.conn.execute(
                "SELECT id, metric, value, unit, observed_at, valid_from, valid_to, metadata "
                "FROM observation WHERE subject_id IN (?, ?) "
                "ORDER BY observed_at DESC LIMIT 1",
                (hit.id, scene_id),
            ).fetchone()
            if observation is not None:
                metadata["observation"] = {
                    "id": str(observation["id"]),
                    "metric": str(observation["metric"]),
                    "value": float(observation["value"]),
                    "unit": observation["unit"],
                    "observed_at": str(observation["observed_at"]),
                    "valid_from": observation["valid_from"],
                    "valid_to": observation["valid_to"],
                    **(
                        meta
                        if isinstance(
                            meta := _load_json(observation["metadata"]), dict
                        )
                        else {}
                    ),
                }

            locator.update(
                {
                    "scene_id": scene_id,
                    "revision_id": revision_id,
                    "asset_id": asset_id,
                    "collection_id": collection_id,
                }
            )
            hit.metadata = metadata
            hit.locator = locator
        return hits

    def _expand_relation_context(self, hits: list[SearchHit]) -> list[SearchHit]:
        """Append supplementary segments linked to entities referenced by the top hits."""
        from geomemory.storage.repositories.entity_repo import EntityRepository

        max_supplementary = 50
        supplementary: list[SearchHit] = []
        seen_segment_ids: set[str] = set(h.id for h in hits)

        for hit in hits:
            seg_id = hit.id
            entities = EntityRepository(self.conn).get_by_evidence(seg_id)
            for entity in entities:
                entity_relations = self.conn.execute(
                    "SELECT * FROM relation WHERE source_id = ? OR target_id = ?",
                    (entity.id, entity.id),
                ).fetchall()
                for rel in entity_relations:
                    other_id = (
                        str(rel["target_id"])
                        if str(rel["source_id"]) == entity.id
                        else str(rel["source_id"])
                    )
                    rel_segments = self.conn.execute(
                        "SELECT * FROM segment WHERE id = ?", (other_id,)
                    ).fetchall()
                    for seg_row in rel_segments:
                        if seg_row["id"] not in seen_segment_ids:
                            seen_segment_ids.add(seg_row["id"])
                            seg = SegmentRepository(self.conn).get(seg_row["id"])
                            if seg is not None:
                                supplementary.append(
                                    SearchHit(
                                        id=seg.id,
                                        text=seg.text or "",
                                        metadata={**seg.metadata, "modality": "relation"},
                                    )
                                )
                        if len(supplementary) >= max_supplementary:
                            break
                    if len(supplementary) >= max_supplementary:
                        break
                if len(supplementary) >= max_supplementary:
                    break
            if len(supplementary) >= max_supplementary:
                break
        return supplementary

    def _fts_search(self, query: str, *, top_k: int, collections: list[str] | None) -> list[SearchHit]:
        """Run a FTS5 full-text query over segment text."""
        if not query:
            return []
        rows = self._fts_match(query, top_k, collections)
        hits: list[SearchHit] = []
        for r in rows:
            try:
                meta = json.loads(r["metadata"]) if r["metadata"] else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}
            hits.append(
                SearchHit(
                    id=r["id"],
                    sparse_score=float(r["score"]),
                    text=r["text"],
                    locator=json.loads(r["locator"]),
                    metadata={
                        "modality": "text",
                        "segment_type": r["segment_type"],
                        "revision_id": r["revision_id"],
                        **meta,
                    },
                )
            )
        return hits

    def _fts_match(self, query: str, top_k: int, collections: list[str] | None) -> list[Any]:
        """Return FTS5 match rows (safely wrapping the MATCH syntax)."""
        terms = [t for t in _FTS_TERM_RE.findall(query) if t.strip()]
        if not terms:
            return []
        escaped_terms = [f'"{t.replace(chr(34), "")}"' for t in terms if t.strip()]
        if not escaped_terms:
            return []
        fts_query = " OR ".join(escaped_terms)
        sql = (
            "SELECT s.id, s.text, s.locator, s.revision_id, s.segment_type, s.metadata, "
            "bm25(segments_fts) AS score "
            "FROM segments_fts JOIN segment s ON s.rowid = segments_fts.rowid "
            "WHERE segments_fts MATCH ? "
        )
        params: list[Any] = [fts_query]
        if collections:
            placeholders = ",".join("?" for _ in collections)
            sql += " AND s.revision_id IN (SELECT id FROM asset_revision WHERE asset_id IN "
            sql += f"(SELECT id FROM asset WHERE collection_id IN ({placeholders})))"
            params.extend(collections)
        sql += " ORDER BY score LIMIT ?"
        params.append(top_k)
        try:
            return self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("FTS MATCH query failed for %r: %s", fts_query, exc)
            return []

    def _dense_search(
        self, query: str, *, top_k: int, collections: list[str] | None = None
    ) -> list[SearchHit]:
        """Dense search over the persisted index, falling back to n-gram TF.

        When a persisted index exists for the active space it is used;
        otherwise a NumpyBackend is built on demand from SQLite so search
        always works offline. Collection-filtered queries use the on-demand
        backend because the persisted index is global.
        """
        if collections:
            return self._numpy_dense_search(query, top_k=top_k, collections=collections)
        space_id = self.active_space_id
        try:
            from geomemory.services.index_service import IndexService

            hits = IndexService(
                self.conn,
                self.index_dir,
                settings=self.settings,
                batch_size=self.settings.batch_size,
            ).search(
                query,
                space_id=space_id,
                top_k=top_k,
                model_path=self.settings.embedding_path,
            )
            if hits:
                for hit in hits:
                    hit.metadata.setdefault("modality", "text")
                return hits
        except (ImportError, RuntimeError, ValueError) as exc:
            # Fall through to the on-demand n-gram backend.
            logger.warning("dense search with persisted index failed: %s", exc)
        except Exception:
            logger.warning("unexpected dense-search error; falling back to ngram", exc_info=True)
        return self._numpy_dense_search(query, top_k=top_k, collections=collections)

    def _numpy_dense_search(
        self, query: str, *, top_k: int, collections: list[str] | None = None
    ) -> list[SearchHit]:
        """Ngram-based vector search over stored segments (no model required)."""
        try:
            from geomemory.index.numpy_backend import NumpyBackend
        except ImportError:
            return []
        backend = NumpyBackend.from_database(self.conn, collections=collections)
        if backend.count() == 0:
            return []
        request = SearchRequest(query=query, mode="dense", top_k=top_k, top_n=top_k)
        hits = backend.search(request)
        for hit in hits:
            hit.metadata.setdefault("modality", "text")
        return hits

    def _candidate_search(self, query: str, top_k: int = 20) -> list[SearchHit]:
        """Search candidate memories with tier weighting."""
        try:
            from geomemory.feedback.candidate_memory import CandidateMemoryRepository
            from geomemory.feedback.scoring import MemoryScorer
        except ImportError:
            return []
        try:
            repo = CandidateMemoryRepository(self.conn)
            scorer = MemoryScorer()
            cands = repo.search(query, min_score=0)
            hits: list[SearchHit] = []
            for cm in cands[:top_k]:
                weight = scorer.weight_for_state(cm.state)
                if cm.state == "rejected":
                    continue
                hits.append(
                    SearchHit(
                        id=cm.id,
                        score=weight,
                        dense_score=weight,
                        text=cm.content,
                        metadata={
                        "modality": "text",
                        "candidate_state": cm.state,
                        "confidence": cm.confidence_score,
                    },
                    )
                )
            return hits
        except (ImportError, RuntimeError, ValueError) as exc:
            logger.warning("candidate memory search failed: %s", exc)
            return []
        except Exception:
            logger.warning("unexpected candidate search error", exc_info=True)
            return []

    def _merge_candidate_hits(self, authoritative: list[SearchHit], candidates: list[SearchHit], top_n: int = 20) -> list[SearchHit]:
        """Merge candidate hits after authoritative results with tier weights (authoritative dominates)."""
        # authoritative weight 1.0 always higher than candidate max 0.8
        # Append candidates after authoritative, capped.
        merged = list(authoritative)
        for h in candidates:
            if len(merged) >= top_n:
                break
            if h.id not in {x.id for x in merged}:
                merged.append(h)
        return merged[:top_n]



# ──────────────────────────────────────────────────────────────────────────────
# Public API class
# ──────────────────────────────────────────────────────────────────────────────


class _WorkspaceSearchAdapter(SearchService):
    """Adapt ``SearchMixin.search`` to the SearchService interface used by QA."""

    def __init__(
        self,
        workspace: SearchMixin,
        *,
        collections: list[str] | None = None,
        modalities: Literal["text", "image", "both"] | None = None,
        modality_weight: float = 0.7,
    ) -> None:
        super().__init__([])
        self._workspace = workspace
        self._collections = collections
        self._modalities = modalities
        self._modality_weight = modality_weight

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 20,
        top_n: int = 5,
        filters: SearchFilters | None = None,
        modalities: Literal["text", "image", "both"] | None = None,
        modality_weight: float = 0.7,
    ) -> SearchResult:
        effective_modalities = modalities if modalities is not None else self._modalities
        effective_weight = (
            modality_weight if modality_weight != 0.7 else self._modality_weight
        )
        return self._workspace.search(
            query,
            mode=mode,
            top_k=top_k,
            top_n=top_n,
            collections=self._collections,
            spatial=filters.spatial if filters else None,
            temporal=filters.temporal if filters else None,
            sensor=filters.sensors if filters else None,
            modalities=effective_modalities,
            modality_weight=effective_weight,
        )


