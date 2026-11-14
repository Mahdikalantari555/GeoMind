"""Embedding-model hub surface of the workspace facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geomemory.core.models import (
    Turn,
)
from geomemory.core.workspace_knowledge import KnowledgeMixin


class ModelsMixin(KnowledgeMixin):
    @staticmethod
    def list_models_global(workspace_dir: Path | str | None = None, embedding_path: Path | str | None = None) -> list[dict[str, Any]]:
        """Return the embedding model hub inventory without requiring an open workspace."""
        from geomemory.embeddings.hub import EmbeddingModelHub

        return EmbeddingModelHub(
            workspace_dir=Path(workspace_dir) if workspace_dir else None,
            embedding_path=Path(embedding_path) if embedding_path else None,
        ).scan()

    def list_available_models(self) -> list[dict[str, Any]]:
        """Return the embedding model hub inventory."""
        from geomemory.embeddings.hub import EmbeddingModelHub

        return EmbeddingModelHub(
            workspace_dir=self.path,
            embedding_path=self.settings.embedding_path,
        ).scan()

    def download_model(self, name: str, backend: str) -> dict[str, Any]:
        """Download an embedding or vision model by name and backend."""
        if backend == "vision":
            from geomemory.embeddings.vision_downloader import download_vision_model

            path = download_vision_model(self.settings)
            return {"name": name, "backend": backend, "path": path}
        from geomemory.embeddings.hub import EmbeddingModelHub

        hub = EmbeddingModelHub(
            workspace_dir=self.path,
            embedding_path=self.settings.embedding_path,
        )
        path = hub.download(name, backend=backend)
        entry = hub.find_model(name, backend=backend)
        return entry or {"name": name, "backend": backend, "path": path}

    def get_turn(self, turn_id: str) -> Turn | None:
        """Return a conversation turn by id, or None."""
        from geomemory.storage.repositories.conversation_repo import TurnRepository

        return TurnRepository(self.conn).get(turn_id)

    def download_vision_model(self) -> str | None:
        """Download the vision model for this workspace and return its path."""
        from geomemory.embeddings.vision_downloader import download_vision_model as _download

        return _download(self.settings)
