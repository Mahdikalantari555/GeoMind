# Tasks: harden-sqlite-write-contention

## 1. geomemory storage

- [ ] 1.1 `write_with_retry(conn, fn, attempts, base_delay_s)` with
      exponential backoff → `DatabaseError` on residual busy
- [ ] 1.2 `thread_safe_connect(db_path)` — RLock-guarded connection
- [ ] 1.3 Contention tests: second-connection write succeeds under retry;
      reader-during-write does not corrupt; residual busy maps to
      `DatabaseError`

## 2. geolearn sidecar DBs

- [x] 2.1 busy_timeout PRAGMA on `geolearn.db` connections
      (training_pipeline `_init_db`/writes, persistence ClassifierStore)

## 3. Quality

- [ ] 3.1 pytest + ruff + mypy --strict green (geomemory, geolearn)
