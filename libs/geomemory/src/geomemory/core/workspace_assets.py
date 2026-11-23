"""Asset inspection, stats, and index management capability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geomemory.core.models import (
    Asset,
    AssetDetail,
)
from geomemory.core.workspace_ingest import IngestMixin


class AssetsMixin(IngestMixin):
    # ── Index ────────────────────────────────────────────────────────────────

    def build_index(self, space_id: str | None = None) -> None:
        """Build the retrieval index for a space.

        Embeds all segments (via the configured embedding model, or the
        offline hashing embedder) and persists a dense index under
        ``index_dir/<space_id>``. Already-embedded segments are skipped, so
        repeated calls are incremental.
        """
        from geomemory.services.index_service import IndexService

        target_space = space_id or self.active_space_id
        service = IndexService(
            self.conn,
            self.index_dir,
            settings=self.settings,
            batch_size=self.settings.batch_size,
        )
        service.build(target_space, model_path=self.settings.embedding_path)
        self._index_space = target_space

    def rebuild_index(self, space_id: str | None = None) -> None:
        """Rebuild the index for a space from SQLite source."""
        from geomemory.services.index_service import IndexService

        target_space = space_id or self.active_space_id
        service = IndexService(
            self.conn,
            self.index_dir,
            settings=self.settings,
            batch_size=self.settings.batch_size,
        )
        service.rebuild(target_space, model_path=self.settings.embedding_path)
        self._index_space = target_space


    # ── Inspection ──────────────────────────────────────────────────────────

    def get_workspace_path(self) -> Path:
        """Return the resolved filesystem path of this workspace."""
        return self.path

    def list_assets(
        self,
        collection_id: str | None = None,
        *,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[Asset]:
        """List assets, optionally filtered by collection with pagination."""
        from geomemory.storage.repositories.asset_repo import AssetRepository

        repo = AssetRepository(self.conn)
        if collection_id is None:
            return repo.list_all(limit=limit, offset=offset)
        return repo.get_by_collection(collection_id)

    def inspect(self, asset_id: str) -> AssetDetail:
        """Return a full inspection view of an asset."""
        asset = self._asset_by_id(asset_id)
        revision = self._revision_by_id(asset.current_revision_id) if asset.current_revision_id else None
        segments = self._segments_for_revision(asset.current_revision_id or "") or []
        scenes: list[Any] = []
        layers: list[Any] = []
        observations: list[Any] = []
        if revision is not None:
            from geomemory.storage.repositories.spatial_repo import (
                ObservationRepository,
                RasterSceneRepository,
                VectorLayerRepository,
            )

            scenes = RasterSceneRepository(self.conn).get_by_revision(revision.id)
            layers = VectorLayerRepository(self.conn).get_by_revision(revision.id)
            for scene in scenes:
                observations.extend(
                    ObservationRepository(self.conn).get_by_subject(scene.id)
                )
        return AssetDetail(
            asset=asset,
            revision=revision,
            collections=(
                [c] if (c := self.get_collection(asset.collection_id)) is not None else []
            ),
            segments=segments,
            scenes=scenes,
            layers=layers,
            observations=observations,
        )


    # ── Overview stats ─────────────────────────────────────────────────────

    def get_index_manifest(self, space_id: str | None = None) -> dict[str, Any] | None:
        """Return the manifest for a space (or active space) as a dict, or None."""
        target_space = space_id or self.active_space_id
        from geomemory.index.manifest import load_manifest

        space_dir = self.index_dir / target_space
        if (space_dir / "manifest.json").is_file():
            try:
                return load_manifest(space_dir).model_dump(mode="json")
            except Exception:
                pass
        if (self.index_dir / "manifest.json").is_file():
            try:
                manifest = load_manifest(self.index_dir)
                if not space_id or manifest.space_id == space_id:
                    return manifest.model_dump(mode="json")
            except Exception:
                pass
        return None

    def stats(self) -> dict[str, Any]:
        """Return lightweight workspace statistics for dashboards.

        Includes collection/asset/segment counts, spatial index usage, index
        manifest state, feedback counts, and storage footprint. All values are
        JSON-serializable and derived from the workspace itself.
        """
        collections = self.list_collections()
        assets = [a for a in self.list_assets()]
        revision_ids = {a.current_revision_id for a in assets if a.current_revision_id}

        segment_counts = {
            row["revision_id"]: int(row["c"])
            for row in self.conn.execute(
                "SELECT revision_id, COUNT(*) AS c FROM segment GROUP BY revision_id"
            ).fetchall()
        }
        segments = sum(segment_counts.get(rev_id, 0) for rev_id in revision_ids)

        scene_counts = {
            row["revision_id"]: int(row["c"])
            for row in self.conn.execute(
                "SELECT revision_id, COUNT(*) AS c FROM raster_scene GROUP BY revision_id"
            ).fetchall()
        }
        scene_count = sum(scene_counts.get(rev_id, 0) for rev_id in revision_ids)

        vector_counts = {
            row["revision_id"]: int(row["c"])
            for row in self.conn.execute(
                "SELECT revision_id, COUNT(*) AS c FROM vector_layer GROUP BY revision_id"
            ).fetchall()
        }
        vector_count = sum(vector_counts.get(rev_id, 0) for rev_id in revision_ids)
        obs_row = self.conn.execute("SELECT COUNT(*) AS c FROM observation").fetchone()
        observation_count = int(obs_row["c"]) if obs_row is not None else 0

        from geomemory.storage.repositories.feedback_repo import (
            DatasetExampleRepository,
            FeedbackRepository,
        )

        feedback_count = FeedbackRepository(self.conn).count()
        pending_review = len(
            DatasetExampleRepository(self.conn).list_by_state("pending")
        )

        from geomemory.storage.repositories.spatial_repo import SpatialRepository

        spatial_entities = SpatialRepository(self.conn).count()

        index_manifest = self.get_index_manifest()

        db_bytes = self.db_path.stat().st_size if self.db_path.is_file() else 0
        objects_bytes = 0
        objects_dir = self.objects_dir
        if objects_dir.is_dir():
            for p in objects_dir.rglob("*"):
                if p.is_file():
                    objects_bytes += p.stat().st_size

        return {
            "collections": len(collections),
            "assets": len(assets),
            "segments": segments,
            "raster_scenes": scene_count,
            "vector_layers": vector_count,
            "observations": observation_count,
            "spatial_entities": spatial_entities,
            "feedback_events": feedback_count,
            "pending_review": pending_review,
            "index_manifest": index_manifest,
            "storage_bytes": db_bytes + objects_bytes,
            "db_bytes": db_bytes,
            "objects_bytes": objects_bytes,
            "settings": self.settings.model_dump(),
        }


    # ── Image search (experimental, vision embeddings) ─────────────────────

    def image_index(self) -> Any:
        """Return the persisted image index manager (empty when none exists)."""
        from geomemory.index.image_index import ImageIndex

        index_dir = self.index_dir / "image"
        if (index_dir / "manifest.json").is_file():
            try:
                return ImageIndex.load(index_dir)
            except (OSError, ValueError):
                return ImageIndex()
        return ImageIndex()

    def search_images(self, query_vector: Any, *, top_k: int = 10) -> list[dict[str, Any]]:
        """Search vision-embedded raster tiles by image vector (experimental)."""
        hits = self.image_index().search(query_vector, top_k=top_k)
        return list(hits)

