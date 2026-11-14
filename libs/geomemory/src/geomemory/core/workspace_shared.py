"""Shared workspace constants, logger, JSON helper, and attribute
annotations for the split facade (change: split-workspace-facade)."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from geomemory.core.events import EventBus
from geomemory.core.models import WorkspaceSettings
from geomemory.storage.asset_layout import AssetLayout
from geomemory.storage.object_store import ObjectStore

WORKSPACE_MARKER = ".geomemory"
DB_FILENAME = "geomemory.db"
SETTINGS_FILENAME = "workspace.yaml"

logger = logging.getLogger(__name__)

# Default storage directory names (can be overridden via settings).
DEFAULT_OBJECTS_DIR = "objects"
DEFAULT_INDEX_DIR = "indexes"
DEFAULT_LOGS_DIR = "logs"


logger = logging.getLogger("geomemory.core.workspace")


def _load_json(value: Any) -> dict[str, Any] | list[Any]:
    """Parse a SQLite JSON column without letting corrupt metadata abort search."""
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, (dict, list)) else {}


class WorkspaceAttrs:
    """Shared instance attributes set by ``Workspace.__init__``.

    Mixins inherit these annotations so mypy --strict sees a complete
    ``self`` surface without each mixin re-declaring state.
    """

    conn: sqlite3.Connection
    path: Path
    settings: WorkspaceSettings
    _settings: WorkspaceSettings
    events: EventBus
    objects: ObjectStore
    layout: AssetLayout
    db_path: Path
    objects_dir: Path
    index_dir: Path
    logs_dir: Path
    _closed: bool
    _index_space: str | None
