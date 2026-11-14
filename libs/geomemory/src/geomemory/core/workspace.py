"""Workspace lifecycle and the public GeoMemory class."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from geomemory.core.config import load_settings, save_settings, settings_from_dict
from geomemory.core.events import (
    EventBus,
)
from geomemory.core.exceptions import (
    WorkspaceNotFoundError,
)
from geomemory.core.models import (
    WorkspaceConfig,
    WorkspaceSettings,
)
from geomemory.core.workspace_models import ModelsMixin
from geomemory.core.workspace_shared import (
    DB_FILENAME,
    DEFAULT_OBJECTS_DIR,
    SETTINGS_FILENAME,
    WORKSPACE_MARKER,
)
from geomemory.storage import connect, initialize, migrate, schema_sql
from geomemory.storage.asset_layout import AssetLayout
from geomemory.storage.object_store import ObjectStore


class Workspace(ModelsMixin):
    """A GeoMemory workspace.

    To create or open a workspace use :class:`GeoMemory` (the public entry
    point). This class wires the SQLite database, object store, and indexes
    together.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        create: bool = False,
        config: WorkspaceConfig | None = None,
    ) -> None:
        self.path = Path(path)
        self._closed = False
        self.events = EventBus()

        if create:
            self._create(config or WorkspaceConfig())
        else:
            self._open_existing()
        self.settings = self._settings

        self.db_path = self.path / DB_FILENAME
        self.objects_dir = self.path / self.settings.objects_dir
        self.index_dir = self.path / self.settings.index_dir
        self.logs_dir = self.path / self.settings.logs_dir

        # Connection uses check_same_thread=False so it survives Streamlit
        # rerun threads (each rerun runs in a different OS thread). Streamlit
        # serializes script execution, so access is effectively single-threaded
        # at the application level; the connection is never shared concurrently.
        self.conn = connect(self.db_path)
        initialize(self.conn)
        migrate(self.conn, schema_sql())

        self.objects = ObjectStore(self.path / DEFAULT_OBJECTS_DIR)
        self.layout = AssetLayout(self.path)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def _create(self, config: WorkspaceConfig) -> None:
        if self.path.exists() and any(self.path.iterdir()):
            from geomemory.core.exceptions import WorkspaceExistsError

            raise WorkspaceExistsError(
                f"Cannot create workspace at {self.path}: directory is not empty"
            )
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / WORKSPACE_MARKER).touch()
        settings = settings_from_dict(config.model_dump())
        save_settings(self.path / SETTINGS_FILENAME, settings)
        self._settings = settings

    def _open_existing(self) -> None:
        if not (self.path / WORKSPACE_MARKER).is_file():
            raise WorkspaceNotFoundError(
                f"No GeoMemory workspace found at {self.path} "
                f"(missing {WORKSPACE_MARKER} marker)"
            )
        self._settings = load_settings(self.path / SETTINGS_FILENAME)

    def update_settings(self, **changes: Any) -> WorkspaceSettings:
        """Update and persist workspace settings (validated).

        Accepts any ``WorkspaceSettings`` field, e.g. ``model_path``,
        ``embedding_path``, ``batch_size``. Returns the updated settings.
        """
        merged = self._settings.model_dump()
        for key, value in changes.items():
            if key not in WorkspaceSettings.model_fields:
                raise ValueError(f"Unknown setting: {key}")
            merged[key] = value
        updated = WorkspaceSettings(**merged)
        save_settings(self.path / SETTINGS_FILENAME, updated)
        self._settings = updated
        self.settings = updated
        return updated

    def close(self) -> None:
        """Close the database connection."""
        if not self._closed:
            self.conn.close()
            self._closed = True

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()



class GeoMemory(Workspace):
    """Public entry point for the GeoMemory library.

    Usage::

        memory = GeoMemory.open("./workspace")
        collection = memory.create_collection("papers")
        job = memory.ingest("paper.pdf", collection_id=collection.id)
        results = memory.search("vegetation indices")
        answer = memory.ask("Which indices detect crop stress?")
    """

    @classmethod
    def open(cls, path: str | Path) -> GeoMemory:
        """Open an existing workspace."""
        return cls(path, create=False)

    @classmethod
    def create(cls, path: str | Path, config: WorkspaceConfig | None = None) -> GeoMemory:
        """Create a new workspace."""
        return cls(path, create=True, config=config)


