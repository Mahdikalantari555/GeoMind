# Plan 005: Serialize background-job and collection writes behind the platform write lock

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- server/src/geofront_api/routers/data.py server/src/geofront_api/routers/collections.py server/src/geofront_api/routers/models.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none (but plan 007's concurrency tests would pin this plan
  harder — order flexible)
- **Category**: bug (invariant enforcement)
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

AGENTS.md invariant 2: all write operations serialize behind the asyncio
write lock in `server/src/geofront_api/state.py` (SQLite single-writer,
one active workspace). Most routers honor it, but three write paths bypass
it: the scene-download background job calls `ws.ingest(...)` from a worker
thread unlocked, the collections create/archive routes write unlocked, and
the model-training job touches the workspace unlocked. The shared
`GeoMemory` facade holds **one SQLite connection** (`check_same_thread=False`)
whose docstring says "Callers must already serialize access" — unlocked
writers can interleave implicit transactions with concurrent request
handlers and surface `database is locked` / corrupted partial states.

## Current state

- **The correct exemplar** — `routers/ingest.py:68-116` wraps its ingest job
  in an async closure that takes the lock on the main loop:
  ```python
  async def _run() -> dict[str, object]:
      def _sync_ingest() -> dict[str, object]:
          with tempfile.TemporaryDirectory(prefix="gf-ingest-") as tmp:
              ...  # ws.ingest(...)
      # (somewhere below: async with get_state().write_lock:
      #     payload = await run_in_threadpool(_sync_ingest))
  ```
  Read the whole `_make_ingest_job` in `ingest.py` before starting — it is
  the pattern to copy.
- **Violator 1** — `routers/data.py:97-139`: the scene-download job is a
  **sync** closure (runs in a worker thread via `jobs.py:151`) that calls
  `_ensure_scenes_collection(ws)` (a write: `ws.create_collection` when
  missing, data.py:55-60) and `ws.ingest(Path(band_path), collection.id, ...)`
  (data.py:116-128) with **no lock**. The download itself
  (`fetch_scene`, data.py:104-112) is remote I/O and needs NO lock.
- **Violator 2** — `routers/collections.py:34-42` and `:54-64`:
  ```python
  @router.post("", status_code=201)
  async def create_collection(req: CreateCollectionRequest) -> dict[str, object]:
      ws = _require_ws()
      try:
          col = await run_in_threadpool(ws.create_collection, req.name, req.description or "")
  ...
  @router.delete("/{collection_id}")
  async def archive_collection(collection_id: str) -> dict[str, object]:
      ...
          archived = await run_in_threadpool(ws.archive_collection, collection_id)
  ```
  Writes with no `async with get_state().write_lock:` (compare
  `routers/workspace.py:261-265` `workspace_stats` which wraps even a read
  in the lock — the house pattern is `async with lock: return await run_in_threadpool(fn)`).
- **Violator 3** — `routers/models.py:171-190`: the `model_train` job runs
  `TrainingPipeline(geolearn_dir, candidate_source=ws)` +
  `pipeline.train_on_feedback(...)` in a sync worker-thread closure.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Server tests | `conda run -n geo pytest server/tests -q` | 156 passed baseline |
| Integration tests | `conda run -n geo pytest tests -q` | 8 passed |
| Server lint | `conda run -n geo ruff check server` | exit 0 |
| Server typecheck | `cd server && conda run -n geo mypy --strict src/` | exit 0 |

## Scope

**In scope**:
- `server/src/geofront_api/routers/data.py` (download job closure)
- `server/src/geofront_api/routers/collections.py`
- `server/src/geofront_api/routers/models.py` (train/rollback jobs/routes —
  investigation + targeted locking, see Step 3)
- `server/tests/test_collections_lock.py` (create)

**Out of scope**:
- `libs/**` — do not touch geomemory or geolearn. If training turns out to
  write through the facade, the fix is still gateway-side (wrap the call),
  but a deeper lib-side fix is a separate change.
- `jobs.py`, `state.py`, SSE, event payloads.
- PERF work (lock scope narrowing for /ask) — explicitly NOT this plan.

## Git workflow

- Branch: `advisor/005-job-write-lock`
- Commits: `fix(server): take the write lock for scene-download asset registration`, `fix(server): serialize collection create/archive behind the write lock`, `fix(server): guard model-training workspace writes with the write lock`

## Steps

### Step 1: Convert the scene-download job to the async-closure pattern

Restructure `data.py`'s download job (keep the same job type, events, and
result shape):

```python
def _run(job_id: str) -> dict[str, Any]:
    # Phase A (unlocked): remote download — no workspace writes here.
    def _download() -> FetchResult-like:
        return fetch_scene(req.scene_id, req.roi, ..., progress_cb=_progress, dest=dest)

    # Phase B (locked): collection ensure + per-band ingest.
    def _register(result) -> dict[str, Any]:
        collection = _ensure_scenes_collection(ws)
        for band, band_path in sorted(result.band_files.items()):
            ...  # ws.ingest(...) exactly as today
        return {...}  # the same result dict as today

    return _register(_download())  # replaced in the async wrapper below
```

then submit an async closure that mirrors `ingest.py`'s `_make_ingest_job`:

```python
async def _run_locked(job_id: str) -> dict[str, Any]:
    result = await run_in_threadpool(_download)
    async with get_state().write_lock:
        return await run_in_threadpool(_register, result)

record = await get_job_manager().submit("scene_download", _run_locked)
```

Notes:
- `get_job_manager().update_progress(...)` callbacks inside `_download` are
  thread-safe (they publish via EventBus) — keep them.
- Keep `record.type`, progress events, and the returned dict byte-for-byte
  compatible (`server/tests/test_data_routes.py` and
  `tests/integration/` pin them).

**Verify**: `conda run -n geo pytest server/tests/test_data_routes.py -q` → all pass; `conda run -n geo pytest tests -q` → 8 passed.

### Step 2: Lock the collections write routes

In `collections.py`, wrap both write routes:

```python
async with get_state().write_lock:
    col = await run_in_threadpool(ws.create_collection, req.name, req.description or "")
```

(and the archive equivalent). List/get routes stay unlocked. Keep the
`get_event_bus().publish` calls **outside** the lock (publishing under a
lock is unnecessary; current code publishes after the call).

**Verify**: `conda run -n geo pytest server/tests -q` → 156 passed.

### Step 3: Investigate and guard the training job

1. Read `libs/geolearn/src/geolearn/training_pipeline.py` and list every
   call it makes on `candidate_source` / the workspace facade.
2. Classify each call: read-only (`get_*`, `list_*`, `search_*`) vs write
   (`create_*`, `update_*`, `ingest`, `review_*`, `commit`-level).
3. If the pipeline's ws usage is **read-only**: add a comment on the job
   closure stating that, and do not take the lock (holding it for a
   minutes-long training run would starve the gateway). Also wrap the
   `ModelVersionManager` file writes check — they write under
   `<ws>/geolearn/` (separate files, no SQLite) — no lock needed.
4. If the pipeline **writes** through ws: wrap only those write call sites
   by passing a small adapter object into `TrainingPipeline(candidate_source=...)`
   that acquires nothing (it can't — sync thread) but instead records them;
   then STOP and report the list, because the correct fix (async job closure
   + lock around writes, as in Step 1) changes training latency behavior
   and needs an owner decision.
5. Also check the rollback route in `models.py` (referenced by
   `server/tests/test_model_train.py:108-137`): if it writes via the
   facade, wrap it in `async with get_state().write_lock:` exactly like
   Step 2.

**Verify**: `conda run -n geo pytest server/tests/test_model_train.py -q` → all pass.

### Step 4: Regression test for collection serialization

Create `server/tests/test_collections_lock.py`: assert that while a
collection create is in flight, a concurrent ingest is not interleaved
corruptly. Practical simplification matching existing test infra: monkeypatch
`ws.create_collection` to sleep 0.3 s, then fire the POST and an
`/ingest/bytes` request concurrently (pattern of plan 004's dispatch test);
assert both succeed with correct envelopes and the workspace stats stay
consistent. If concurrency testing with the current fixtures is not
feasible after one attempt, pin the simpler contract instead: the routes
acquire the lock (assert via monkeypatching `state.write_lock.acquire` /
`locked()` flag) and report the downgrade.

**Verify**: `conda run -n geo pytest server/tests/test_collections_lock.py -q` → passes.

## Test plan

- New: `server/tests/test_collections_lock.py`.
- Existing `test_data_routes.py`, `test_model_train.py`, integration suite
  must pass unchanged.
- Verification: full server suite + integration suite green.

## Done criteria

- [ ] `grep -n "ws.ingest" server/src/geofront_api/routers/data.py` shows the
      ingest calls only inside the locked phase
- [ ] `conda run -n geo pytest server/tests -q` → all pass (156 + new)
- [ ] `conda run -n geo pytest tests -q` → 8 passed
- [ ] `conda run -n geo ruff check server` → exit 0
- [ ] `cd server && conda run -n geo mypy --strict src/` → exit 0
- [ ] Training-job classification documented in the commit message or report
- [ ] No `libs/**` changes; no files outside scope modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- The ingest exemplar in `routers/ingest.py` has drifted (no async closure /
  no lock) — the pattern this plan copies is gone; report.
- Step 3 finds geolearn's training pipeline writing through the facade —
  report the call list; do not invent an adapter-based locking scheme
  unilaterally.
- Converting the download job to an async closure breaks the
  `job.progress` events or result shape in a way the existing tests
  detect — two fix attempts, then report.

## Maintenance notes

- This plan deliberately does NOT narrow the /ask lock scope (PERF-07) —
  that redesign must come after this plan and after the concurrency tests
  (plan 007) exist.
- The unused `thread_safe_connect`/`write_with_retry` helpers in
  `libs/geomemory/storage/database.py` are related debt; a lib-side change
  proposal is the right vehicle, not this plan.
- Reviewer should scrutinize: no long-running remote I/O under the lock
  (only registration is locked); event payloads unchanged.
