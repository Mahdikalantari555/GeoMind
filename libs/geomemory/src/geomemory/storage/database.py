"""SQLite connection management with WAL mode, foreign keys, and migrations."""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from geomemory.core.exceptions import DatabaseError

T = TypeVar("T")

# Base schema is stored alongside this module as schema.sql.
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# PRAGMAs applied to every connection.
_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=30000",
)


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys enabled.

    The connection is returned with ``row_factory`` set to
    :class:`sqlite3.Row` and ``detect_types`` enabled for declared types.

    ``check_same_thread`` is disabled so the connection can be reused across
    worker threads (e.g. Streamlit reruns). Callers must already serialize
    access — see :func:`thread_safe_connect` for a locked wrapper.
    """
    try:
        conn = sqlite3.connect(
            str(db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,
        )
    except sqlite3.Error as exc:
        raise DatabaseError(f"Failed to open database at {db_path}: {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        for pragma in _PRAGMAS:
            conn.execute(pragma)
    except sqlite3.Error as exc:
        conn.close()
        raise DatabaseError(f"Failed to configure database: {exc}") from exc
    return conn


def schema_sql() -> str:
    """Return the raw content of schema.sql."""
    return _SCHEMA_PATH.read_text(encoding="utf-8")


def initialize(conn: sqlite3.Connection) -> None:
    """Apply the base schema (idempotent)."""
    try:
        conn.executescript(schema_sql())
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"Failed to initialize database schema: {exc}") from exc


def integrity_check(conn: sqlite3.Connection) -> list[str]:
    """Run ``PRAGMA integrity_check`` and return the result rows."""
    rows = conn.execute("PRAGMA integrity_check").fetchall()
    return [str(r[0]) for r in rows]


def is_healthy(conn: sqlite3.Connection) -> bool:
    """Return True if the database passes integrity_check."""
    return all(row == "ok" for row in integrity_check(conn))


class _LockedConnection:
    """An RLock-guarded SQLite connection safe for cross-thread use.

    Every operation serializes behind one lock per connection, so a single
    ``check_same_thread=False`` connection can be shared by threads without
    external synchronization.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    @property
    def raw(self) -> sqlite3.Connection:
        """The underlying connection — for helpers that need direct access."""
        return self._conn

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executescript(self, sql: str) -> None:
        with self._lock:
            self._conn.executescript(sql)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "_LockedConnection":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def thread_safe_connect(db_path: str | Path) -> _LockedConnection:
    """Open a WAL-mode connection guarded by an RLock (cross-thread safe)."""
    return _LockedConnection(connect(db_path))


def write_with_retry(
    conn: sqlite3.Connection,
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay_s: float = 0.05,
) -> T:
    """Run a write callable with bounded exponential backoff on lock errors.

    ``busy_timeout`` covers most contention; this adds a bounded retry for
    the residual "database is locked" that surfaces when the timeout
    expires. On exhaustion the last error is re-raised as
    :class:`DatabaseError` with context.
    """
    delay = base_delay_s
    for attempt in range(1, attempts + 1):
        try:
            result = fn()
            conn.commit()
            return result
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            locked = "locked" in message or "busy" in message
            if not locked or attempt == attempts:
                raise DatabaseError(
                    f"SQLite write failed after {attempt} attempt(s): {exc}"
                ) from exc
            time.sleep(delay)
            delay *= 2
    raise DatabaseError("SQLite write retry loop exited unexpectedly")  # pragma: no cover
