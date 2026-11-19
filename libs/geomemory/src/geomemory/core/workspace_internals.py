"""Internal lookup/retrieval-run helpers shared by all workspace mixins."""



from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from geomemory.core.exceptions import AssetNotFoundError
from geomemory.core.models import Asset, AssetRevision, RetrievalRun, Segment
from geomemory.core.models import Workspace as WorkspaceModel
from geomemory.core.workspace_shared import WorkspaceAttrs


class InternalsMixin(WorkspaceAttrs):
    # ── Internal helpers ────────────────────────────────────────────────────

    @contextmanager
    def _write_tx(self) -> Iterator[None]:
        """Commit the workspace writes together, or roll back on failure.

        The caller owns serialization; callees must not commit independently.
        """
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def _workspace_id(self) -> str:
        row = self.conn.execute("SELECT id FROM workspace LIMIT 1").fetchone()
        if row is not None:
            return str(row["id"])
        # First access: register this workspace.
        ws = WorkspaceModel(name=self.settings.name, settings=self.settings.model_dump())
        self.conn.execute(
            "INSERT INTO workspace (id, name, settings, created_at) VALUES (?, ?, ?, ?)",
            (ws.id, ws.name, json.dumps(ws.settings), ws.created_at),
        )
        self.conn.commit()
        return ws.id

    def _asset_by_id(self, asset_id: str) -> Asset:
        from geomemory.storage.repositories.asset_repo import AssetRepository

        asset = AssetRepository(self.conn).get(asset_id)
        if asset is None or asset.deleted_at is not None:
            raise AssetNotFoundError(f"Asset not found: {asset_id}")
        return asset

    def _revision_by_id(self, revision_id: str) -> AssetRevision | None:
        from geomemory.storage.repositories.asset_repo import AssetRevisionRepository

        return AssetRevisionRepository(self.conn).get(revision_id)

    def _segments_for_revision(self, revision_id: str) -> list[Segment] | None:
        from geomemory.storage.repositories.segment_repo import SegmentRepository

        segments = SegmentRepository(self.conn).get_by_revision(revision_id)
        if not segments:
            return None
        return segments

    def _save_retrieval_run(self, run: RetrievalRun, results: list[dict[str, Any]]) -> None:
        self.conn.execute(
            "INSERT INTO retrieval_run (id, turn_id, query, query_plan, filters, config, candidates, results, latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)",
            (
                run.id,
                run.turn_id,
                run.query,
                json.dumps(run.query_plan),
                json.dumps(run.filters),
                json.dumps(run.config),
                json.dumps(results),
                run.latency_ms,
                run.created_at,
            ),
        )
        self.conn.commit()
    @property
    def active_space_id(self) -> str:
        """Resolve active embedding space_id from explicit build state, settings, or manifests."""
        if getattr(self, "_index_space", None):
            return str(self._index_space)
        # 1. Try resolving from active embedder provider
        try:
            from geomemory.embeddings.factory import build_text_embedder

            embedder = build_text_embedder(self.settings)
            space_id = getattr(embedder, "space_id", None)
            if space_id:
                return str(space_id)
        except Exception:
            pass
        # 2. Try resolving via hub summary
        try:
            from geomemory.embeddings.hub import EmbeddingModelHub

            provider = getattr(self.settings, "embedding_provider", None) or getattr(
                self.settings, "embedding_backend", "onnx"
            )
            model_name = getattr(self.settings, "onnx_model_name", "Xenova/all-MiniLM-L6-v2")
            if provider == "cloudflare":
                model_name = getattr(self.settings, "cloudflare_model_id", "@cf/baai/bge-base-en-v1.5")
            summary = EmbeddingModelHub().summary(active_backend=provider, active_model=model_name)
            if summary.get("active_space_id"):
                return str(summary["active_space_id"])
        except Exception:
            pass
        # 3. Check for existing manifests under index_dir
        if hasattr(self, "index_dir") and self.index_dir.is_dir():
            try:
                for child in self.index_dir.iterdir():
                    if child.is_dir() and (child / "manifest.json").is_file():
                        return child.name
            except Exception:
                pass
        return "text.hash.v1"
