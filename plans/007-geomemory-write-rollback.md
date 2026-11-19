# Plan 007: Roll back multi-write geomemory operations on failure

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- libs/geomemory/src/geomemory/core/workspace_ingest.py libs/geomemory/src/geomemory/core/workspace_qa.py libs/geomemory/src/geomemory/core/workspace_internals.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/006-ask-citation-fk-fix.md (land first — it edits
  the same `workspace_qa.py` region; this plan then wraps it)
- **Category**: bug (data integrity)
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

`Workspace.ingest` and the QA persistence path execute multiple INSERTs and
an UPDATE in one implicit SQLite transaction, committed only at the end —
with **no rollback on failure**. If any step raises (vision embed failure,
`persist_scene` error, citation insert), the exception surfaces as a 500 but
the half-written transaction stays open on the shared connection. The next
unrelated successful operation's `commit()` (e.g. a search's retrieval-run
save) silently persists ghost rows: assets with `current_revision_id = NULL`,
orphaned segments, conversations without answers. That corrupts `list_assets`,
stats, and the provenance chain the product is built on.

## Current state

- `libs/geomemory/src/geomemory/core/workspace_ingest.py:104-197` — the
  write body: `INSERT INTO asset` (:114), `INSERT INTO asset_revision`
  (:127), per-chunk `INSERT INTO segment` (:152), `persist_scene` /
  `persist_vector_layer` + vision embed (:168-192), `UPDATE asset SET
  current_revision_id` (:194), single `self.conn.commit()` (:197). No
  try/except around any of it.
- `libs/geomemory/src/geomemory/core/workspace_qa.py:106-179` —
  conversation + user/assistant turns + answer + citations, single
  `self.conn.commit()` (:179). Same absence of rollback.
- `libs/geomemory/src/geomemory/core/workspace_internals.py:16-51` — the
  `InternalsMixin` where shared helpers live (this is where the new
  context manager belongs).
- Dedup early-return path (`workspace_ingest.py:71-88`) performs no writes
  before returning — must remain untouched.
- SQLite connection: `storage/database.py:28-37` `connect()` — WAL mode,
  `check_same_thread=False`; callers must serialize (gateway lock per
  plan 005).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| geomemory tests (baseline FIRST) | `cd libs/geomemory && conda run -n geo pytest tests -q` | record the failure set (known pre-existing Windows failures: CLI dashboard check, lance backend, olmoearth multichannel) |
| geomemory tests (after) | same | identical failure set |
| Lint | `conda run -n geo ruff check libs/geomemory/src` | exit 0 |
| mypy | `cd libs/geomemory && conda run -n geo mypy --strict src/` | no NEW errors vs baseline (~46 pre-existing) |

Lib discipline: `fix(geomemory): ...` commits, one concern per commit.

## Scope

**In scope**:
- `libs/geomemory/src/geomemory/core/workspace_internals.py` (add
  `_write_tx` context manager)
- `libs/geomemory/src/geomemory/core/workspace_ingest.py` (wrap the write
  body)
- `libs/geomemory/src/geomemory/core/workspace_qa.py` (wrap the persistence
  body)
- New unit test file under `libs/geomemory/tests/unit/`

**Out of scope**:
- Other mixins' single-statement write+commit pairs (e.g. collection
  create) — safe already; only multi-write bodies are wrapped.
- `storage/database.py` (the unused retry/connect helpers) — separate
  lib change.
- Any change to method signatures, return shapes, or event emissions.

## Git workflow

- Branch: `advisor/007-geomemory-write-rollback`
- Commit: `fix(geomemory): roll back multi-write transactions on failure`

## Steps

### Step 1: Record the baseline

Run the geomemory suite once; save the failure list for comparison.

### Step 2: Add a `_write_tx` context manager to `InternalsMixin`

In `workspace_internals.py`:

```python
from contextlib import contextmanager

@contextmanager
def _write_tx(self):
    """Run multi-statement writes atomically: rollback on any failure.

    The facade shares one SQLite connection; an exception mid-write would
    otherwise leave an open transaction that a later commit() persists
    (ghost assets / orphaned segments). Caller still owns serialization.
    """
    try:
        yield self.conn
        self.conn.commit()
    except BaseException:
        self.conn.rollback()
        raise
```

(`BaseException` so cancellation also rolls back; re-raise unchanged.)

**Verify**: `cd libs/geomemory && conda run -n geo mypy --strict src/` → no new errors.

### Step 3: Wrap the two write bodies

- `workspace_ingest.py`: in `ingest`, wrap from the first
  `self.conn.execute("INSERT INTO asset ...")` through
  `self.conn.execute("UPDATE asset SET current_revision_id ...")` in
  `with self._write_tx():`, and delete the trailing `self.conn.commit()`
  (the context manager commits). The dedup early-return block above stays
  outside the `with`. Note: the parse/chunk step and `self.objects.put_bytes`
  (:101) do no DB writes — keep them outside the transaction to avoid
  holding a write txn during heavy CPU/IO work.
- `workspace_qa.py`: wrap the body of the persistence function from
  `ConversationRepository(self.conn).create(conv)` through the citation
  loop in `with self._write_tx():` and remove its trailing
  `self.conn.commit()`.

Careful: helpers called inside the wrapped region must not call
`self.conn.commit()` themselves (that would end the transaction early).
Grep the callees (`persist_scene`, `persist_vector_layer`,
`try_embed_vision`, repository `.create` methods) for `commit()` calls —
if any commit internally, STOP and report (that callee would need the same
treatment, which expands scope).

**Verify**: `cd libs/geomemory && conda run -n geo pytest tests -q` → identical failure set to baseline.

### Step 4: Regression test

New unit test (file next to the existing ingest unit tests — find them with
`ls libs/geomemory/tests/unit | grep -i ingest`):

1. Build a workspace; monkeypatch a downstream callee to raise after the
   first DB write — e.g. patch `geomemory.rs.persist.persist_scene` to
   `raise RuntimeError("boom")` for a raster ingest, or patch the citation
   INSERT region by feeding a broken citation.
2. Call `ws.ingest(...)` (or the QA persist path) inside
   `pytest.raises(RuntimeError)`.
3. Assert the transaction left nothing behind:
   `SELECT COUNT(*) FROM asset` == 0, `SELECT COUNT(*) FROM asset_revision` == 0,
   and `self.conn.in_transaction is False` after the call (rolled back).
4. Then perform a normal unrelated write (e.g. `ws.create_collection`) and
   assert it succeeds — proving no ghost state poisons later commits.

**Verify**: `conda run -n geo pytest <new test> -q` → passes.

## Test plan

- New rollback unit tests (ingest path + QA path).
- Full geomemory suite: baseline failure set unchanged.
- Repo-root integration suite (`conda run -n geo pytest tests -q`) → 8 passed.

## Done criteria

- [ ] `grep -n "self.conn.rollback" libs/geomemory/src/geomemory/core/workspace_internals.py` → 1 hit (the context manager)
- [ ] geomemory suite: identical failure set to baseline
- [ ] `conda run -n geo pytest tests -q` → 8 passed
- [ ] New tests exist and pass
- [ ] `conda run -n geo ruff check libs/geomemory/src` → exit 0
- [ ] mypy: no new errors vs baseline
- [ ] No files outside scope modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- A callee inside the wrapped region commits internally (breaks atomicity)
  — report the file:line list; wrapping that callee is a scope decision.
- Any existing test relies on partial-commit behavior (would now roll back)
  — report; do not "fix" the test to expect corruption.
- The mixin hierarchy changed and `_write_tx` placement is ambiguous —
  report.

## Maintenance notes

- All future multi-write facade methods should use `self._write_tx()`;
  mention this in the lib's AGENTS.md if it has a conventions section
  (one-line addition is in scope).
- Plan 005 (gateway write-lock enforcement) + this plan together close the
  write-integrity gap: serialization at the gateway, atomicity in the lib.
- Reviewer should scrutinize: no commit() left inside wrapped regions;
  dedup early-return path untouched.
