# Plan 006: Stop candidate-memory citations from violating the citation foreign key

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- libs/geomemory/src/geomemory/core/workspace_qa.py libs/geomemory/src/geomemory/qa/citation.py libs/geomemory/src/geomemory/core/workspace_search.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none (land before plan 007 if both touch
  `workspace_qa.py`; the two edits are adjacent)
- **Category**: bug
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

When the hybrid search fuses in "candidate memory" hits (learned corrections
stored in their own table), their hit ids are **candidate-memory ids**, not
segment ids. If the LLM cites one of those context indices, citation
persistence inserts `segment_id = <candidate id>` into the `citation` table,
whose schema declares `segment_id TEXT NOT NULL REFERENCES segment(id)` with
`PRAGMA foreign_keys=ON` — an `IntegrityError`. Because `ws.ask` has no
error handling around persistence, the gateway returns a 500 **after a
successful answer was generated**, exactly in the situation where
authoritative context was thin (which is when candidates surface at all).

## Current state

- `libs/geomemory/src/geomemory/core/workspace_search.py:477-489` —
  candidate hits carry the candidate id:
  ```python
  hits.append(
      SearchHit(
          id=cm.id,              # ← candidate_memory.id, not a segment id
          score=weight,
          dense_score=weight,
          text=cm.content,
          metadata={
              "modality": "text",
              "candidate_state": cm.state,
              "confidence": cm.confidence_score,
          },
      )
  )
  ```
- `libs/geomemory/src/geomemory/qa/citation.py:29-39` — `map_citations`
  copies `hit.id` into `Citation.segment_id` verbatim.
- `libs/geomemory/src/geomemory/core/workspace_qa.py:160-178` — the
  persistence loop has exactly one exemption, for raster tiles:
  ```python
  for citation in answer.citations:
      citation.answer_id = answer_row.id
      # Image scenes are valid QA sources but are not rows in ``segment``.
      # Keep them in the returned citation list without violating the
      # text-segment foreign key in the persistence schema.
      if citation.locator.get("target_type") == "raster_tile":
          continue
      self.conn.execute(
          "INSERT INTO citation (id, answer_id, segment_id, locator, claim_span, created_at) "
          "VALUES (?, ?, ?, ?, ?, ?)",
          (...citation.segment_id...),
      )
  ```
- `libs/geomemory/src/geomemory/storage/schema.sql:279-286` —
  `segment_id TEXT NOT NULL REFERENCES segment(id)`; `database.py:22` sets
  `PRAGMA foreign_keys=ON`.
- Candidate hits' `locator` is the SearchHit default (empty dict) — they do
  NOT get the `raster_tile` exemption, so they reach the INSERT.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| geomemory tests (baseline FIRST — record failures) | `cd libs/geomemory && conda run -n geo pytest tests -q` | run before any edit; known pre-existing Windows failures: CLI dashboard check, lance backend, olmoearth multichannel (see `tasks/todo.md`) |
| geomemory tests (after edit) | same command | same failure set as baseline, all others green |
| Lint | `conda run -n geo ruff check libs/geomemory/src` | exit 0 |
| Typecheck | `cd libs/geomemory && conda run -n geo mypy --strict src/` | expect the ~46 documented pre-existing errors — do not add new ones; compare error count against baseline |

**Important**: changes to `libs/geomemory` follow the lib's own release
discipline — one concern per commit, `fix(geomemory): ...` style.

## Scope

**In scope**:
- `libs/geomemory/src/geomemory/core/workspace_qa.py` (persistence loop only)
- `libs/geomemory/tests/...` (new unit test — place near existing QA tests;
  find them with `ls libs/geomemory/tests/unit | grep -i qa`)

**Out of scope**:
- `qa/citation.py` — mapping logic stays generic.
- `workspace_search.py` — candidate hits keep their ids (they are used
  elsewhere, e.g. UI display and candidate scoring).
- Schema changes, alternative persistence for candidate citations — a
  separate openspec change if the owner wants candidate citations queryable.

## Git workflow

- Branch: `advisor/006-ask-citation-fk-fix`
- Commit: `fix(geomemory): skip citation persistence for non-segment sources`

## Steps

### Step 1: Record the baseline

Run the geomemory suite once and note the failure list. Every pre-existing
failure must fail the same way after your change.

**Verify**: paste the baseline summary into your report.

### Step 2: Guard non-segment citations at persistence

Extend the exemption in `workspace_qa.py` so any citation whose
`segment_id` is not an actual segment row is skipped from persistence (kept
in the returned model, like raster tiles):

```python
for citation in answer.citations:
    citation.answer_id = answer_row.id
    # Image scenes are valid QA sources but are not rows in ``segment``.
    if citation.locator.get("target_type") == "raster_tile":
        continue
    # Candidate memories (learned corrections) surface as QA sources with
    # candidate-memory ids; they are not segment rows either. Keep them in
    # the returned citations, skip persistence (schema.sql: FK to segment).
    exists = self.conn.execute(
        "SELECT 1 FROM segment WHERE id = ? LIMIT 1", (citation.segment_id,)
    ).fetchone()
    if exists is None:
        continue
    self.conn.execute(...)
```

The SELECT-before-INSERT is deliberate over checking
`metadata["candidate_state"]`: it is robust to ANY future non-segment
source (candidate ids, future memory types) and costs one indexed lookup per
citation (idx_citation_segment / segment PK).

**Verify**: `cd libs/geomemory && conda run -n geo pytest tests -q` → same failure set as baseline.

### Step 3: Add the regression test

Find the existing QA/ask unit tests (`ls libs/geomemory/tests/unit | grep -iE "qa|ask|citation"` and the integration test
`tests/integration/test_gateway_core_roundtrip.py` at repo root for the
end-to-end pattern). New unit test in the matching location:

1. Build a workspace (see any existing workspace unit fixture).
2. Create a candidate memory via the facade
   (`ws.create_candidate_memory(content=..., source_feedback_ids=[])` — check
   the exact signature in `workspace_models.py` or the candidate-memory
   service) and mark it accepted/scored so search surfaces it.
3. Drive `ws.ask` with a stub LLM backend whose answer text cites the
   candidate index (e.g. answer `"... [1]"` where sources[0] is the
   candidate hit). Follow how existing tests stub the backend
   (search `AbstainBackend` / fake backend usage in `libs/geomemory/tests`).
4. Assert: no exception raised; the returned answer text unchanged; the
   persisted citations exclude the candidate id (`SELECT segment_id FROM citation WHERE answer_id = ...` does not contain the candidate id).

**Verify**: `conda run -n geo pytest <new test file> -q` → passes.

## Test plan

- New unit test as in Step 3 (happy path + the FK regression).
- Baseline/after comparison for the whole geomemory suite.
- Repo-root integration suite (`conda run -n geo pytest tests -q`) → 8 passed
  (it exercises ask-with-citations end-to-end).

## Done criteria

- [ ] geomemory suite: identical failure set to baseline, all else green
- [ ] `conda run -n geo pytest tests -q` → 8 passed
- [ ] New regression test exists and passes
- [ ] `conda run -n geo ruff check libs/geomemory/src` → exit 0
- [ ] mypy error count ≤ baseline count (no new errors introduced)
- [ ] No files outside scope modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- The persistence loop in `workspace_qa.py` no longer matches the excerpt
  (renamed, restructured, or moved) — report.
- Existing QA tests stub the LLM backend in a way that makes a
  candidate-citing answer impossible to construct — report what you found;
  do not build a new stubbing framework.
- The `segment` table check fails because citations may legitimately
  reference another table's ids in current tests — report (would change the
  intended fix).

## Maintenance notes

- Candidate citations are now returned-but-not-persisted; if the product
  later wants them queryable ("which corrections influenced this answer"),
  that is a schema decision — proposal an openspec change (`candidate
  citation` table or a `source_type` column), not a silent re-enable.
- Plan 007 wraps this same function region with rollback handling — land
  006 first, then 007 builds on it.
