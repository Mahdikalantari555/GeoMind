# Plan 004: Dispatch all blocking agent/tool calls to the threadpool

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- server/src/geofront_api/routers/agent/`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug / perf
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

The gateway runs a single uvicorn worker with one event loop. Four agent
routes call the sync `registry.call(...)` (LLM-backed tools and playbooks,
deadlines up to 880 s) **directly inside async handlers**, and several other
agent routes run filesystem globs and raw SQLite on the loop. While any of
them runs, the whole gateway is unresponsive: all HTTP requests stall and
SSE keepalives (`: ping` every 15 s) stop, so every connected browser sees
the gateway as offline. AGENTS.md invariant 4 states blocking facade calls
must run in a threadpool (`anyio.to_thread`) — this plan enforces that on
the agent router family.

## Current state

Direct `registry.call` on the event loop (all inside `async def` handlers):

- `server/src/geofront_api/routers/agent/chat.py:212`
  ```python
  result = registry.call(effective_name, effective_args, ctx)
  dump: dict[str, Any] = result.model_dump(mode="json")
  return dump
  ```
  (`/agent/run` — tool or playbook; playbook deadline `time.monotonic() + 880.0` at `chat.py:194`)
- `server/src/geofront_api/routers/agent/tools.py:71`
  ```python
  result = registry.call(tool_name, body.args, ctx)
  ```
  (`/agent/tools/{tool_name}/call`)
- `server/src/geofront_api/routers/agent/farms.py:537`
  ```python
  result = registry.call("geo_recommend", args, ctx)
  ```
  (`/agent/farms/{farm_id}/recommend` — an LLM advisor tool)

Blocking scans/DB on the event loop (sync helpers called directly from async
handlers):

- `farms.py:59-132` `_find_farms_geojson` — recursive
  `root.glob("**/*.geojson")` plus `json.loads` of every candidate and
  object-store blob reads (`farms.py:101-117`); called from async handlers
  `list_farms`/`get_farm`/report handlers (farms.py:249, 288, 432).
- `farms.py:163-184` `_report_dirs` — nested globs.
- `routers/agent/maps.py:56-98` `_collect_artifacts` —
  `root.glob("runs/**/*")` invoked from async `list_maps`.
- `routers/agent/conversations.py` — `service.store.list_conversations()`
  and raw `store.conn.execute(...)` on the loop.
- `routers/agent/files.py` — `workspace.glob(pattern)` on the loop.

**The correct exemplar** already in the same file family —
`chat.py:71-80` (streaming chat) wraps the LLM call in a thread:

```python
def run_chat() -> str:
    text: str = core.chat(...)
    return text

task = asyncio.create_task(asyncio.to_thread(run_chat))
```

and route-level blocking facade calls elsewhere use
`from fastapi.concurrency import run_in_threadpool` (see
`routers/collections.py:30`). `run_in_threadpool` is the house style for
one-shot sync calls; use it.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Server tests | `conda run -n geo pytest server/tests -q` | 156 passed baseline |
| Server lint | `conda run -n geo ruff check server` | exit 0 |
| Server typecheck | `cd server && conda run -n geo mypy --strict src/` | exit 0 |

## Scope

**In scope**:
- `server/src/geofront_api/routers/agent/chat.py` (the `/agent/run` handler
  only — NOT the streaming chat SSE path, already correct)
- `server/src/geofront_api/routers/agent/tools.py`
- `server/src/geofront_api/routers/agent/farms.py`
- `server/src/geofront_api/routers/agent/maps.py`
- `server/src/geofront_api/routers/agent/conversations.py`
- `server/src/geofront_api/routers/agent/files.py`
- `server/tests/test_agent_dispatch.py` (create — see Test plan)

**Out of scope**:
- `libs/geoagent/**` — the registry and tools stay sync; dispatch is the
  caller's job.
- `server/src/geofront_api/routers/agent/playbooks.py` `run_playbook`
  — it calls the **playbook tool** via `registry.call` too; include it in
  Step 1 if it has the same inline call (check it; the playbook run route is
  at playbooks.py:92-130). Do not change the list/validate routes.
- JobManager, SSE, write-lock semantics (plan 005's territory).

## Git workflow

- Branch: `advisor/004-event-loop-dispatch`
- Commits: `fix(server): dispatch agent tool calls to the threadpool`, `fix(server): move agent file scans off the event loop`

## Steps

### Step 1: Wrap the three `registry.call` sites in `run_in_threadpool`

At `chat.py:212`, `tools.py:71`, `farms.py:537` (and the playbook run route
if it has the same inline call):

```python
from fastapi.concurrency import run_in_threadpool  # add to imports

result = await run_in_threadpool(registry.call, effective_name, effective_args, ctx)
```

Keep the `RunContext` construction on the loop (it is cheap and sync).
Note `run_in_threadpool` passes positional args — verify each call's arg
order (`registry.call(name, args_dict, ctx)` everywhere).

**Verify**: `conda run -n geo ruff check server` → exit 0; `cd server && conda run -n geo mypy --strict src/` → exit 0.

### Step 2: Move the scan helpers off the loop

For each site below, wrap the blocking helper invocation in
`run_in_threadpool` (the helpers themselves stay sync):

- `farms.py`: in `list_farms`, `get_farm`, and the report handlers, wrap
  the `_find_farms_geojson(...)` / `_report_dirs(...)` calls:
  `found = await run_in_threadpool(_find_farms_geojson)`.
- `maps.py`: wrap `_collect_artifacts(...)` inside `list_maps`.
- `conversations.py`: wrap `service.store.list_conversations()` and any
  `store.conn.execute` reads in `run_in_threadpool`; prefer existing store
  methods over raw `conn.execute` when one exists.
- `files.py`: wrap `workspace.glob(pattern)` (and the file read if it reads
  content on the loop) in `run_in_threadpool`.

Do not change response shapes, status codes, or error envelopes.

**Verify**: `conda run -n geo pytest server/tests -q` → 156 passed (all agent
route tests still green).

### Step 3: Add a regression test proving the loop stays free

Create `server/tests/test_agent_dispatch.py`:

- Register (or monkeypatch) a tool whose callable sleeps ~0.5 s.
- Using the app's test client, fire `/agent/tools/{name}/call` as a task and
  concurrently request `/health`; assert `/health` completes in well under
  the tool duration (e.g. < 0.2 s) — proving the tool did not occupy the
  loop. Follow `server/tests/test_agent.py` for client/app fixture setup
  and `test_farms.py` for how tools get stubbed. If the test client cannot
  run two requests concurrently (it is portal-based), use
  `httpx.AsyncClient` with `ASGITransport(app=app)` and `asyncio.gather` —
  check what other server tests already use and match it.
- If a concurrency assertion proves impossible with the existing test
  infrastructure after one honest attempt, downgrade the test to: the
  endpoint returns the same result as before the refactor (contract pin),
  and note the downgrade in your report.

**Verify**: `conda run -n geo pytest server/tests/test_agent_dispatch.py -q` → passes.

## Test plan

- New: `server/tests/test_agent_dispatch.py` (concurrency or contract pin —
  see Step 3 escape hatch).
- Existing suites (test_agent.py, test_farms.py, test_job_progress.py) must
  stay green without modification.
- Verification: `conda run -n geo pytest server/tests -q` → 157 passed.

## Done criteria

- [ ] `grep -rn "= registry.call(" server/src/geofront_api/routers/agent/ | grep -v run_in_threadpool | grep -v to_thread` → only hits inside threadpool-wrapped
      coroutines or none at all (paste output in report)
- [ ] `conda run -n geo pytest server/tests -q` → 157 passed
- [ ] `conda run -n geo ruff check server` → exit 0
- [ ] `cd server && conda run -n geo mypy --strict src/` → exit 0
- [ ] No files outside scope modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- A `registry.call` site is inside a function that cannot be awaited
  (non-async context where `run_in_threadpool` isn't available) — report;
  do not restructure the handler.
- Wrapping `store.conn.execute` calls in conversations.py requires changing
  the store class (`libs/geoagent`) — report instead of editing the lib.
- The existing agent tests fail after the mechanical wrap (they shouldn't —
  the calls are semantically identical) — two attempts, then report.

## Maintenance notes

- Reviewer should scrutinize: every new `run_in_threadpool` call passes the
  same arg order as the original call; no response shape changed.
- The streaming chat path (`chat.py:71-130`) intentionally keeps its own
  `asyncio.to_thread` + queue pattern — leave untouched.
- Future agent routes must follow this pattern; consider a ruff lint rule
  later (out of scope here).
