"""SQLite connection helper for geolearn's own sidecar databases.

All geolearn databases (``geolearn.db``, caches) live beside their owner's
workspace and may be written while the host process is busy, so every
connection sets a busy timeout — without it, contention surfaces as an
immediate ``sqlite3.OperationalError: database is locked``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

BUSY_TIMEOUT_MS = 30000


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    """Open a geolearn sidecar SQLite connection with a busy timeout."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn
