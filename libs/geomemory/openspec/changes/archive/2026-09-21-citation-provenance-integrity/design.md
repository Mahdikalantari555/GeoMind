## Context

`qa/chat_service.py:119` calls `map_citations("", gen.text, context)` with an empty string as `answer_id`. The `Answer` row is inserted in `workspace.py:_persist_answer()` AFTER the chat service returns, but the citations created during chat service execution have no parent answer reference. This breaks the provenance chain `answer → citation → segment → asset_revision → objects/<sha256>` at the application layer.

## Goals / Non-Goals

**Goals:**
- Fix the citation answer_id linkage so provenance is complete
- Add a regression test
- Verify _persist_answer() remains correct post-fix

**Non-Goals:**
- Changing the Answer or Citation Pydantic models
- Adding new database columns
- Modifying the server API response shape
- Fixing other provenance gaps (e.g., segment→asset linkage)

## Decisions

### D1: Persist answer before mapping citations
**Choice**: In `chat_service.py`, execute the answer INSERT first, get the generated ID, then call `map_citations(answer_id, ...)`.
**Rationale**: The answer ID is needed at citation-creation time, not after. This requires reordering the persistence logic.

### D2: _persist_answer simplification
**Choice**: After D1, `_persist_answer()` in `workspace.py` may redundantly set `citation.answer_id` again (from the already-correct value). This is harmless but can be cleaned up.
**Rationale**: Leave as-is for minimal risk; mark as optional cleanup.

### D3: Regression test scope
**Choice**: Add one focused test in `libs/geomemory/tests/unit/test_qa.py` (or similar) that mocks the LLM backend and asserts `QAResult.citations[0].answer_id` is non-empty and matches the DB row.
**Rationale**: Unit-level is sufficient; integration tests already cover the full flow.

## Risks / Trade-offs

- **[Risk] Transaction ordering**: Inserting answer before citations changes the transaction order. **Mitigation**: Both inserts are in the same transaction; SQLite handles this correctly.
- **[Risk] _persist_answer redundancy**: May write answer_id twice. **Mitigation**: Harmless no-op; can be cleaned up in a follow-on.

## Migration Plan

1. Modify `chat_service.py` to persist answer first, then map citations with the real ID
2. Verify `_persist_answer()` still works (may become partially redundant)
3. Add regression test
4. Run `pytest libs/geomemory/tests -q`
5. Run `pytest server/tests -q` (no server changes expected)
