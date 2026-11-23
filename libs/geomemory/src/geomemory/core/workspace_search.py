"""Hybrid search capability of the workspace facade."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import TYPE_CHECKING, Any, Literal

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
    settings_signature,
)
from geomemory.index.image_backend import ImageRetrievalBackend
from geomemory.retrieval.fusion import rrf_fuse
from geomemory.retrieval.search_service import SearchService, apply_hit_filters

if TYPE_CHECKING:
    from geomemory.index.numpy_backend import NumpyBackend
    from geomemory.services.index_service import IndexService


class SearchMixin(AssetsMixin):
    # ── Cached clients/backends ─────────────────────────────────────────────

    def _cached_index_service(self) -> IndexService:
        """Reuse one IndexService (and its embedder) per settings signature."""
        key = settings_signature(self.settings)
        cache: dict[str, IndexService] = getattr(self, "_index_service_cache", {})
        self._index_service_cache = cache
        if key not in cache:
            from geomemory.services.index_service import IndexService as _IndexService

            cache[key] = _IndexService(
                self.conn,
                self.index_dir,
                settings=self.settings,
                batch_size=self.settings.batch_size,
            )
        return cache[key]

    def _cached_vision_embedder(self) -> Any | None:
        """Build/locate the vision embedder once, not on every image query.

        This also stops the per-query auto-download check (P-072, DEBT-01):
        model discovery is attempted at most once per settings signature.
        """
        key = settings_signature(self.settings)
        cache = getattr(self, "_vision_embedder_cache", None)
        if cache is None:
            cache = {}
            self._vision_embedder_cache = cache
        if key not in cache:
            from geomemory.embeddings.factory import build_vision_embedder

            try:
                cache[key] = build_vision_embedder(self.settings)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vision embedder unavailable for image search: %s", exc)
                cache[key] = None
        return cache[key]

    def _cached_numpy_backend(self, collections: list[str] | None) -> NumpyBackend:
        """Reuse the n-gram backend (and its cached matrix) across queries."""
        db_sig: tuple[Any, ...] = (
            str(self.db_path),
            self.db_path.stat().st_mtime_ns if self.db_path.is_file() else 0,
            self.db_path.stat().st_size if self.db_path.is_file() else 0,
            tuple(collections or ()),
        )
        key = settings_signature(self.settings)
        cache: dict[str, tuple[tuple[Any, ...], NumpyBackend]] = getattr(
            self, "_numpy_backend_cache", {}
        )
        self._numpy_backend_cache = cache
        entry = cache.get(key)
        if entry is None or entry[0] != db_sig:
            from geomemory.index.numpy_backend import NumpyBackend as _NumpyBackend

            backend = _NumpyBackend.from_database(self.conn, collections=collections)
            cache[key] = (db_sig, backend)
            return backend
        return entry[1]

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

        # Final safety net: source-level filters above cover FTS/dense/image,
        # but candidate and relation-expansion paths could still surface a
        # segment whose asset was soft-deleted (M-051).
        fused = self._drop_deleted_hits(fused)

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

    def _drop_deleted_hits(self, hits: list[SearchHit]) -> list[SearchHit]:
        """Remove hits tied to a soft-deleted asset, across every modality."""
        rows = self.conn.execute(
            "SELECT s.id AS segment_id, r.id AS revision_id FROM segment s "
            "JOIN asset_revision r ON r.id = s.revision_id "
            "JOIN asset a ON a.id = r.asset_id "
            "WHERE a.deleted_at IS NOT NULL"
        ).fetchall()
        deleted_segments = {str(row["segment_id"]) for row in rows}
        deleted_revisions = {str(row["revision_id"]) for row in rows}
        return [
            hit
            for hit in hits
            if hit.id not in deleted_segments
            and str(hit.metadata.get("revision_id", "")) not in deleted_revisions
        ]

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

        embedder = self._cached_vision_embedder()
        if embedder is None:
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
        """Attach raster provenance needed by filters, citations, and the UI.

        The original implementation ran one provenance query and one
        observation query per hit (P-073). Both are now fetched in a single
        batched query each.
        """
        if not hits:
            return []
        ids = [hit.id for hit in hits]
        placeholders = ",".join("?" for _ in ids)
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
            f"WHERE rt.id IN ({placeholders}) AND a.deleted_at IS NULL"
        )
        rows = self.conn.execute(sql, ids).fetchall()
        provenance = {str(row["target_id"]): row for row in rows}
        if not provenance:
            return []

        subjects = sorted(
            {hit_id for hit_id in ids if hit_id in provenance}
            | {str(row["scene_id"]) for row in rows}
        )
        subject_placeholders = ",".join("?" for _ in subjects)
        observation_rows = self.conn.execute(
            "SELECT subject_id, id, metric, value, unit, observed_at, valid_from, valid_to, metadata "
            "FROM observation "
            f"WHERE subject_id IN ({subject_placeholders}) ORDER BY observed_at DESC",
            subjects,
        ).fetchall()
        observations: dict[str, Any] = {}
        for observation_row in observation_rows:
            observations.setdefault(str(observation_row["subject_id"]), observation_row)

        kept: list[SearchHit] = []
        for hit in hits:
            row = provenance.get(hit.id)
            if row is None:
                # No traceable, non-deleted asset revision for this tile.
                continue
            metadata = dict(hit.metadata)
            locator = dict(hit.locator)
            metadata["modality"] = "image"
            metadata["target_type"] = "raster_tile"
            metadata["target_id"] = hit.id
            locator.setdefault("target_id", hit.id)
            locator["modality"] = "image"
            locator["target_type"] = "raster_tile"
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

            observation = observations.get(hit.id) or observations.get(scene_id)
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
            kept.append(hit)
        return kept

    def _expand_relation_context(self, hits: list[SearchHit]) -> list[SearchHit]:
        """Append supplementary segments linked to entities in the top hits.

        Entities, relations and segments are fetched in three batched queries
        rather than one per hit/relation (P-073).
        """
        max_supplementary = 50
        if not hits:
            return []
        seen_segment_ids: set[str] = {hit.id for hit in hits}
        hit_ids = [hit.id for hit in hits]
        hit_placeholders = ",".join("?" for _ in hit_ids)
        entity_rows = self.conn.execute(
            f"SELECT id FROM entity WHERE evidence_id IN ({hit_placeholders})", hit_ids
        ).fetchall()
        entity_ids = [str(row["id"]) for row in entity_rows]
        if not entity_ids:
            return []

        entity_placeholders = ",".join("?" for _ in entity_ids)
        relation_rows = self.conn.execute(
            "SELECT source_id, target_id FROM relation WHERE "
            f"source_id IN ({entity_placeholders}) OR target_id IN ({entity_placeholders})",
            [*entity_ids, *entity_ids],
        ).fetchall()
        entity_set = set(entity_ids)
        related_ids: list[str] = []
        for relation in relation_rows:
            source, target = str(relation["source_id"]), str(relation["target_id"])
            other = target if source in entity_set else source
            if other and other not in related_ids:
                related_ids.append(other)
        if not related_ids:
            return []

        related_placeholders = ",".join("?" for _ in related_ids)
        segment_rows = self.conn.execute(
            f"SELECT id, text, metadata FROM segment WHERE id IN ({related_placeholders})",
            related_ids,
        ).fetchall()
        supplementary: list[SearchHit] = []
        for segment_row in segment_rows:
            if len(supplementary) >= max_supplementary:
                break
            if segment_row["id"] in seen_segment_ids:
                continue
            seen_segment_ids.add(segment_row["id"])
            metadata = _load_json(segment_row["metadata"])
            if not isinstance(metadata, dict):
                metadata = {}
            supplementary.append(
                SearchHit(
                    id=str(segment_row["id"]),
                    text=str(segment_row["text"] or ""),
                    metadata={**metadata, "modality": "relation"},
                )
            )
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
            "JOIN asset_revision ar ON ar.id = s.revision_id "
            "JOIN asset a ON a.id = ar.asset_id "
            "WHERE segments_fts MATCH ? AND a.deleted_at IS NULL "
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
            hits = self._cached_index_service().search(
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
            backend = self._cached_numpy_backend(collections)
        except ImportError:
            return []
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


