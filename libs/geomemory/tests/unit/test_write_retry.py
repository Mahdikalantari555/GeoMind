"""Write-contention hardening: bounded retry + cross-thread connections.

Covers ARCHITECTURE.md risk #3 (SQLITE_BUSY with no retry/backoff).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest
from geomemory.core.exceptions import DatabaseError
from geomemory.storage import connect, thread_safe_connect, write_with_retry


def test_retry_success_path(tmp_path: Path) -> None:
    conn = connect(tmp_path / "a.db")
    conn.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")

    def _write() -> int:
        cur = conn.execute("INSERT INTO t (v) VALUES ('x')")
        return cur.rowcount if cur.rowcount is not None else 0

    assert write_with_retry(conn, _write) >= 0
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_retry_maps_residual_busy_to_database_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    conn = connect(tmp_path / "b.db")

    attempts: list[int] = []

    def _always_busy() -> None:
        attempts.append(1)
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr("time.sleep", lambda _s: None)
    with pytest.raises(DatabaseError, match="database is locked"):
        write_with_retry(conn, _always_busy, attempts=3, base_delay_s=0.001)
    assert len(attempts) == 3  # bounded, not infinite


def test_retry_does_not_mask_non_lock_errors(tmp_path: Path) -> None:
    conn = connect(tmp_path / "c.db")

    def _broken() -> None:
        raise sqlite3.OperationalError("near \"x\": syntax error")

    with pytest.raises(DatabaseError, match="syntax error"):
        write_with_retry(conn, _broken, attempts=3)


def test_thread_safe_connect_shares_connection_across_threads(tmp_path: Path) -> None:
    locked = thread_safe_connect(tmp_path / "d.db")
    locked.execute("CREATE TABLE IF NOT EXISTS t (v INTEGER)")

    errors: list[Exception] = []

    def _worker(i: int) -> None:
        try:
            for _ in range(25):
                locked.execute("INSERT INTO t (v) VALUES (?)", (i,))
                locked.commit()
        except Exception as exc:  # noqa: BLE001 — collected for the assert
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert locked.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 100
    locked.close()


def test_second_connection_write_succeeds_with_retry(tmp_path: Path) -> None:
    """The scenario ADR-0003 flags: a second process/connection writing."""
    writer = connect(tmp_path / "e.db")
    writer.execute("CREATE TABLE t (v INTEGER)")

    second = connect(tmp_path / "e.db")

    def _write_on_second() -> None:
        second.execute("INSERT INTO t (v) VALUES (1)")

    # No live contention in this deterministic test — but the retry wrapper
    # must commit transparently through a *different* connection object.
    write_with_retry(second, _write_on_second)
    assert writer.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
