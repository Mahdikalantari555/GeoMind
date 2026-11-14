# Proposal: harden-sqlite-write-contention

> Lib-level change. Lives in `libs/geomemory/openspec/changes/` per the
> per-lib openspec ownership rule (root AGENTS.md).

## Why

ARCHITECTURE.md risk #3: "Single SQLite writer with no retry/backoff —
SQLITE_BUSY risk if a second process ever needs write access." The main
facade connection already sets `PRAGMA busy_timeout=30000` + WAL, but:

- sidecar connections created outside `storage.database.connect` (e.g.
  geolearn's `geolearn.db`, ad-hoc scripts) get **no** busy timeout and
  fail instantly on contention;
- long multi-statement write sections have no bounded retry, so a busy
  timeout expiry surfaces as a raw `sqlite3.OperationalError`.

## What Changes

- `storage/database.py`: add `write_with_retry(conn, fn, *, attempts=4,
  base_delay_s=0.05)` — bounded exponential backoff around a write
  callable, mapping residual `OperationalError("database is locked")` to
  `DatabaseError` with a clear message.
- Export `thread_safe_connect` (docstring already promises it) — a
  `check_same_thread=False` connection guarded by an RLock, for hosts that
  need cross-thread writes outside the gateway's single-writer loop.
- geolearn's own `geolearn.db` connections adopt `busy_timeout` via a
  shared helper (no cross-lib import: geolearn gets a tiny local helper).

## Impact

- **geomemory:** `storage/database.py` + tests (two-connection contention
  test on a temp DB; writer keeps succeeding while a reader holds a
  transaction).
- **geolearn:** `training_pipeline.py`/`persistence.py` sqlite3.connect
  calls gain `PRAGMA busy_timeout`.
- No API change; behavior only under contention.
