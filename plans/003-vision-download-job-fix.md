# Plan 003: Fix the vision-model download job failing after a successful download

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- server/src/geofront_api/routers/models.py server/src/geofront_api/jobs.py server/src/geofront_api/state.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

`POST /api/v1/models/vision/download` downloads a multi-hundred-MB vision
model successfully and then **always fails the job**: the post-download
settings update runs `asyncio.run()` inside a worker thread and tries to
acquire `state.write_lock`, an `asyncio.Lock` already bound to the gateway's
main event loop. On Python ≥3.10 that raises
`RuntimeError: ... is bound to a different event loop`. Consequences: the
job record ends `status="error"`, `vision_path` is never persisted to
workspace settings, and the UI reports a failed install every single time.

## Current state

- `server/src/geofront_api/routers/models.py:108-122`:
  ```python
  def _do_download() -> str:
      path = ws.download_vision_model()
      if path is None:
          raise RuntimeError("Vision model download did not produce a path")

      async def _update_settings() -> None:
          async with state.write_lock:
              await run_in_threadpool(ws.update_settings, vision_path=path)

      asyncio.run(_update_settings())
      return path

  record = await get_job_manager().submit("vision_model_download", _do_download)
  ```
- `server/src/geofront_api/jobs.py:144-151` — the JobManager runs job
  callables in a worker thread (`asyncio.to_thread`) **unless the callable
  is a coroutine function**, in which case it is awaited **on the main
  event loop**:
  ```python
  if asyncio.iscoroutinefunction(fn):
      record.result = (await fn(record.id) if _accepts_job_id(fn) else await fn())
  elif _accepts_job_id(fn):
      record.result = await asyncio.to_thread(fn, record.id)
  else:
      record.result = await asyncio.to_thread(fn)
  ```
- `server/src/geofront_api/state.py:91` — `write_lock: asyncio.Lock`, first
  acquired on the main loop during workspace open/create (all workspace
  routes do `async with state.write_lock`).
- **Exemplar of the correct pattern** — `routers/ingest.py:68-116`
  (`_make_ingest_job`) builds an **async** job closure that takes the write
  lock on the main loop and dispatches blocking work to the threadpool:
  ```python
  async def _run() -> dict[str, object]:
      def _sync_ingest() -> dict[str, object]:
          ...  # blocking ws.ingest(...)
      ...
  ```
  Match this shape.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Server tests | `conda run -n geo pytest server/tests -q` | 156 passed baseline |
| Server lint | `conda run -n geo ruff check server` | exit 0 |
| Server typecheck | `cd server && conda run -n geo mypy --strict src/` | exit 0 |

## Scope

**In scope**:
- `server/src/geofront_api/routers/models.py` (the `_do_download` closure)
- `server/tests/test_models_vision_download.py` (create)

**Out of scope**:
- `libs/**` — `ws.download_vision_model()` and `ws.update_settings` behave
  correctly; the bug is purely in the gateway closure.
- `jobs.py` / `state.py` — JobManager and the lock are correct.
- The other download endpoint (`POST /models/download`, models.py:84) — its
  `_do_download` has no lock use and is fine.

## Git workflow

- Branch: `advisor/003-vision-download-job-fix`
- Commit: `fix(server): run vision-model settings update on the main loop`

## Steps

### Step 1: Convert the job closure to an async function

Rewrite the closure in `models.py` so the lock is taken on the main loop and
blocking work goes to the threadpool (mirroring `ingest.py`'s pattern):

```python
async def _do_download() -> str:
    path = await run_in_threadpool(ws.download_vision_model)
    if path is None:
        raise RuntimeError("Vision model download did not produce a path")

    # Persist vision_path under the platform write lock. This coroutine is
    # awaited on the main event loop by JobManager, so state.write_lock is
    # acquired on the loop it is bound to (see jobs.py dispatch).
    async with state.write_lock:
        await run_in_threadpool(ws.update_settings, vision_path=path)
    return path

record = await get_job_manager().submit("vision_model_download", _do_download)
```

Delete the `asyncio.run(...)` wrapper entirely. Keep the endpoint signature
and 202 behavior unchanged.

**Verify**: `cd server && conda run -n geo mypy --strict src/` → exit 0; `conda run -n geo ruff check server` → exit 0.

### Step 2: Add a regression test

Create `server/tests/test_models_vision_download.py`. Look at
`server/tests/test_job_progress.py` and `server/tests/conftest.py` for how
tests open a workspace and drive the JobManager (conftest isolates gateway
state per test). Structure:

1. Open a workspace via the existing fixture helpers.
2. Monkeypatch `GeoMemory.download_vision_model` (or the facade attribute
   the route calls) to return a temp path without downloading anything —
   e.g. `monkeypatch.setattr(type(ws), "download_vision_model", lambda self: str(tmp_path / "model.onnx"))`
   (adjust to how the facade method is bound; if the method is defined on a
   mixin, patch on `GeoMemory`).
3. `POST /api/v1/models/vision/download` via the app's test client → expect
   202 + `job_id`.
4. Poll `GET /api/v1/jobs/{job_id}` (or await the job manager) until
   terminal; assert final `status == "completed"`.
5. Assert `GET /api/v1/workspace` (or the settings route used by tests)
   now reports `vision_path == <the temp path>`.

If the workspace fixture in conftest opens workspaces read-only or the
settings route shape differs, adapt using an existing settings-update test
(`server/tests/test_workspace.py`) as the pattern.

**Verify**: `conda run -n geo pytest server/tests/test_models_vision_download.py -q` → 1 passed.

## Test plan

- New: `test_models_vision_download.py` — happy path asserts job completes
  AND settings updated (this exact pair is the regression: before the fix,
  the job errors after download).
- Verification: full suite `conda run -n geo pytest server/tests -q` → 157 passed.

## Done criteria

- [ ] `grep -n "asyncio.run" server/src/geofront_api/routers/models.py` → no matches
- [ ] `conda run -n geo pytest server/tests -q` → 157 passed (156 + 1 new)
- [ ] `conda run -n geo ruff check server` → exit 0
- [ ] `cd server && conda run -n geo mypy --strict src/` → exit 0
- [ ] No files outside scope modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- `jobs.py` no longer dispatches coroutine-function jobs on the main loop
  (the `asyncio.iscoroutinefunction(fn)` branch is gone or changed) — the
  fix depends on it; report.
- The test cannot patch `download_vision_model` because the route calls a
  different facade entry point — report what you found rather than
  improvising a deeper refactor.
- `ws.update_settings` signature differs (keyword `vision_path` not
  accepted) — report.

## Maintenance notes

- Any future job closure that must write workspace state should copy this
  async-closure pattern; sync closures in worker threads must never touch
  `state.write_lock`.
- Plan 005 (job write-lock enforcement) touches other job closures — land
  independently; no conflict expected in this file beyond imports.
