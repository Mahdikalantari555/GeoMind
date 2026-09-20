## 1. Fix citation answer_id linkage

- [ ] 1.1 In `libs/geomemory/src/geomemory/qa/chat_service.py`, locate the call to `map_citations("", gen.text, context)` and refactor to: (a) insert answer row first via `self.conn.execute(...)`, (b) commit, (c) fetch the generated answer id, (d) call `map_citations(answer_id, gen.text, context)`
- [ ] 1.2 Verify that `map_citations()` signature accepts the answer_id as its first parameter (check `qa/citation.py`)
- [ ] 1.3 Ensure the answer insert uses the same pattern as `_persist_answer()` in `workspace.py` (same column set, same JSON serialization)

## 2. Verify _persist_answer correctness post-fix

- [ ] 2.1 Read `libs/geomemory/src/geomemory/core/workspace.py:_persist_answer()` and verify it still correctly inserts citations after the chat_service fix
- [ ] 2.2 If `_persist_answer()` redundantly sets `citation.answer_id`, note as optional cleanup — do NOT change in this change (separate task)
- [ ] 2.3 Confirm the database transaction is atomic: answer + all citations committed together

## 3. Regression test

- [ ] 3.1 Add a test in `libs/geomemory/tests/unit/test_qa.py` (or create the file if it doesn't exist) that:
  - Mocks the LLM backend to return an answer with 2+ citations
  - Calls `ws.ask(question)` with a workspace that has indexed content
  - Asserts `result.abstained == False`
  - Asserts `len(result.citations) >= 2`
  - Asserts `result.citations[0].answer_id` is a non-empty UUID string
  - Asserts the answer_id matches the persisted answer row in the DB
- [ ] 3.2 Add a test for the abstention path: when LLM is unavailable, citations SHALL be empty (no regression)

## 4. Verification

- [ ] 4.1 Run `conda run -n geospatial pytest libs/geomemory/tests/unit/test_qa.py -v --tb=short` — new test must pass
- [ ] 4.2 Run `conda run -n geospatial pytest libs/geomemory/tests/ -q --tb=short` — all 503 tests must still pass
- [ ] 4.3 Run `conda run -n geospatial pytest server/tests/test_ask_suggest.py -v --tb=short` — no regression
- [ ] 4.4 Run `conda run -n geospatial ruff check libs/geomemory/src/geomemory/qa/` — no violations
- [ ] 4.5 Run `conda run -n geospatial mypy --strict libs/geomemory/src/geomemory/qa/` — no new type errors
