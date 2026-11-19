# Tasks: add-studio-knowledge-agent

## 1. Resources page (studio-resources)

- [x] 1.1 Drag-drop ingest with batch queue; per-file `job.progress` SSE
      progress; unsupported-type up-front rejection
- [x] 1.2 Collections view (asset counts) + index stats cards (no raw JSON)
- [x] 1.3 Failure recovery: per-file error reason + retry; partial-batch
      results visible
- [x] 1.4 Unit tests: drop validation, queue state, recovery rendering

## 2. Ask page (studio-ask)

- [x] 2.1 Grounded QA view with per-claim grounding states (cited /
      synthesis-informed / uncited)
- [x] 2.2 Citation chips → split view with exact segment (text locator or
      raster metadata)
- [x] 2.3 Abstention state: reason + retrieval snippets + config affordance
      (no error styling)
- [x] 2.4 Search mode with collection/temporal/spatial filters and scores
- [x] 2.5 Unit tests: grounding renderer, abstention renderer, filter logic

## 3. Agent rail (studio-agent-rail)

- [x] 3.1 Streaming chat over SSE; token-by-token render
- [x] 3.2 Plan display with per-step status tracking
- [x] 3.3 Tool trace cards from ToolRun audit records (args, status,
      latency, artifacts, error detail)
- [x] 3.4 `[S#]` citation resolution; invalid keys stripped + flagged in
      metadata
- [x] 3.5 Playbook list/replay (deterministic fast path, same card stream);
      save-from-run
- [x] 3.6 Degraded (no-LLM) state: retrieval-only behavior + config
      affordance, bounded response time
- [x] 3.7 Unit tests: citation stripper, plan tracker, card rendering

## 4. Agent parity tools (studio-agent-parity)

- [x] 4.1 `roi_create` tool → gateway ROI route (same store as UI)
- [x] 4.2 `data_download` tool → gateway download job route (same job as UI)
- [x] 4.3 Unavailability state for `data_download` before
      `add-scene-fetcher` lands (designed, not crash)
- [x] 4.4 Server tests: tools hit same routes/jobs as UI; ToolRun audit rows
      written; artifact SHA-256 identity shared
- [x] 4.5 Regenerate OpenAPI schema; server ruff + mypy --strict + tests pass

## 5. Validation

- [x] 5.1 Studio gates green (check/lint/test); server gates green
- [x] 5.2 Manual scenario: agent draws ROI → downloads → ingests → answers
      with citations, all traceable in UI
