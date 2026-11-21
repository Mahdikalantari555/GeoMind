# Proposal: replace-raw-sql-with-provider-port

> Lib-level change. Lives in `libs/geolearn/openspec/changes/` per the
> per-lib openspec ownership rule (root AGENTS.md).

## Why

`TrainingPipeline` currently reads GeoMemory's `candidate_memory` table via
**raw SQLite** when constructed with a workspace path (the documented
architectural deviation: geolearn opens `geomemory.db` directly, breaking
the facade-only invariant and creating a hidden schema coupling between two
independently versioned libraries). It also soft-imports `geomemory` to open
a *second* facade instance over the same DB — SQLite single-writer risk when
the gateway already holds one.

## What Changes

- Add `geolearn.ports.CandidateMemoryProvider` — a structural typing.Protocol
  over the one operation the pipeline needs:
  `list_candidate_memories(states: list[str] | None) -> Iterable[CandidateLike]`
  where `CandidateLike` has `.id` and `.content` (JSON string).
- `TrainingPipeline(geolearn_dir, candidate_source)` accepts a provider (or
  `None` → no candidates, pending count 0). **No path constructor, no raw
  SQL, no `geomemory` import** — layering is restored: geolearn never reads
  another lib's storage.
- Callers own the wiring:
  - `geoagent/tools/geolearn_tools.py` passes the facade held by
    `memory_tools.get_memory()` (set by the gateway/CLI host), falling back
    to `GeoMemory.open(workspace_dir)` **in geoagent** (geoagent → geomemory
    is the allowed direction), never inside geolearn.
  - The gateway training route (root change `add-studio-training-lab`)
    passes `state.require_workspace()` directly.
- Add optional `progress_cb: Callable[[str, int, int], None]` to
  `train_on_feedback` / `run` — reports `(stage_key, batch_index,
  batch_total)` so background jobs can stream `job.progress` without
  polling. Callback exceptions are isolated from the training path.
- Tests rewritten: the raw-SQL fixture test becomes a fake-provider test;
  the facade mock test stays (it already matches the protocol).

## Impact

- **geolearn:** new `ports.py`; `training_pipeline.py` loses ~60 lines of
  SQL + soft import; minor version intent 0.2.0.
- **geoagent:** `geolearn_tools.py` provider wiring (~10 lines).
- **Consumers unchanged otherwise** — `train_on_feedback` / `run` /
  `pending_count` signatures stay compatible (new kwarg optional).
- Fixes ARCHITECTURE.md deviation #2 (documented in docs update task).
