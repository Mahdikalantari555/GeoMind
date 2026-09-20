## Why

Citation provenance is silently broken: `map_citations("")` in `chat_service.py:119`
passes an empty string as `answer_id`, so every `Citation` object produced by the QA
service carries `answer_id=""`.  The downstream `_persist_answer()` work-around
overwrites the id on insert, but the in-memory `QAResult.citations` returned to the
caller — and therefore to the HTTP API — always contains empty `answer_id` fields,
making the link from answer back to its citations untraceable at the application
layer.  This must be fixed before any client-side provenance UX (click-through from
citations to answers) can be reliable.

## What Changes

- Fix `qa/chat_service.py`: insert the answer row first to obtain its generated id,
  then pass that id into `map_citations()`, so the in-memory `Citation.answer_id` is
  populated before the `QAResult` leaves the service.
- Verify `core/workspace.py::_persist_answer()` remains correct after the fix —
  it currently re-writes `citation.answer_id` from the inserted answer row, which
  should still work but may become a no-op duplication.
- Add regression test(s) asserting `QAResult.citations[i].answer_id` is non-empty
  and equals the persisted answer id.
- (Optional follow-on) expose the citation-level `answer_id` via the server GET /ask
  response schema if it is not already surfaced.

## Capabilities

### New Capabilities

- `citation-provenance`: end-to-end guarantee that every `Citation` in a `QAResult`
  carries a valid, non-empty `answer_id` linking it back to its parent `Answer`,
  preserving the full chain `answer → citation → segment(locator) → asset_revision(hash)`.

### Modified Capabilities

<!-- None — no existing spec requirements are changing; behaviour changes are bug fixes -->

## Impact

| Area | Detail |
|---|---|
| `libs/geomemory/src/geomemory/qa/chat_service.py` | `map_citations` call site: must await answer persistence to get id |
| `libs/geomemory/src/geomemory/core/workspace.py` | `_persist_answer()` flow: may need simplification once answer_id is pre-populated |
| `libs/geomemory/tests/` | New regression test for citation answer_id |
| `server/src/geofront_api/routers/ask.py` | No code change expected; API contract unchanged |
| `apps/web/` | No code change expected; response shape unchanged |
| DB schema | No migration needed — column already exists, just was populated incorrectly |
