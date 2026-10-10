# Tasks

## 1. Doctor Diagnostics & LLM Connectivity (List A #1, #2)

- [x] 1.1 Add active LLM probe test to `server/src/geofront_api/routers/doctor.py` and `libs/geomemory/src/geomemory/services/doctor.py` and verify with test that `GET /api/v1/doctor/llm?test=true` returns latency and reachability.
- [x] 1.2 Update `apps/web/src/features/doctor/DoctorPage.tsx` so uncreated index directories and missing Java display as informational status rather than hard failures, and add a "Test Connection" button on the LLM card.

## 2. Grounded QA & Retrieval Pipelines (List A #3; List B #5, #6)

- [x] 2.1 Remove duplicate `self.search()` call in `Workspace.ask()` in `libs/geomemory/src/geomemory/core/workspace.py` and verify via test that retrieval executes exactly once per question.
- [x] 2.2 Remove `\n\n` from `stop_sequences` in `ChatService.ask()` in `libs/geomemory/src/geomemory/qa/chat_service.py` and verify that multi-paragraph answers are not prematurely truncated.
- [x] 2.3 Update `apps/web/src/features/ask/AskPage.tsx` to display the actual `abstention_reason` exception string when the LLM abstains or is unavailable, instead of a generic configuration message.

## 3. Retrieval Parity, Space ID Resolution & Multilingual Search (List A #7, #8, #13; List B #1, #2, #14)

- [x] 3.1 Update `Workspace._dense_search()` in `libs/geomemory/src/geomemory/core/workspace.py` to resolve active vector space ID dynamically from workspace settings and verify query executes against `sqlite-vec` table when available.
- [x] 3.2 Update `server/src/geofront_api/routers/index.py` and `apps/web/src/api/ops.ts` / `IndexPage.tsx` to use the active space ID by default instead of `text.nomic.v1`, and verify via index router test.
- [x] 3.3 Add `GET /api/v1/index/manifest` endpoint in `server/src/geofront_api/routers/index.py` and update `IndexPage.tsx` to display vector count, dimension, build latency, and active space ID.
- [x] 3.4 Update `_FTS_TERM_RE` and `_fts_match()` in `libs/geomemory/src/geomemory/core/workspace.py` to support Unicode word extraction and dense-only fallback for non-Latin queries, and verify with a Persian test query.

## 4. Agent Runtime Synchronization, Context Scoping & Tool Concurrency (List A #5, #6; List B #3, #4, #11)

- [x] 4.1 Update `AgentService.init()` in `server/src/geofront_api/services/agent.py` to configure `AgentSettings.provider` from `WorkspaceSettings`, and verify the agent initializes with workspace LLM settings.
- [x] 4.2 In `libs/geoagent/src/geoagent/agent.py`, log raw LLM responses, emit a non-empty fallback string when `response.content` is empty/null, and emit SSE `error` events on unhandled backend exceptions.
- [x] 4.3 Add `context_scope` (collections, assets) support to `AgentCore.chat()`, `POST /api/v1/agent/chat`, and add a context picker to `AgentChatPage.tsx`.
- [x] 4.4 Update `memory_tools._get_memory()` in `libs/geoagent/src/geoagent/tools/memory_tools.py` to reuse the active workspace instance under the server write lock instead of opening unmanaged duplicate SQLite connections.
- [x] 4.5 Fix `_feature_bbox` in `libs/geoagent/src/geoagent/tools/advisor_tools.py` to safely handle empty and null geometries, and verify with a unit test.

## 5. Ingestion Chunking, Page Citations & Write Lock Safety (List A #10; List B #7, #13)

- [x] 5.1 Update `PdfLoader` in `libs/geomemory/src/geomemory/ingest/loaders/pdf.py` to track page character offsets and update `HeaderThenTokenChunker` in `libs/geomemory/src/geomemory/ingest/chunkers/header_then_token.py` to assign true page numbers to chunk locators, verifying with a multi-page PDF ingestion test.
- [x] 5.2 Refine `HeaderThenTokenChunker._is_header` to require surrounding blank lines and ignore uppercase acronyms, hashes, and formula fragments.
- [x] 5.3 Enforce `AppState.write_lock` acquisition inside the file ingestion background worker in `server/src/geofront_api/routers/ingest.py`.

## 6. Model Hub, HuggingFace Download & Settings Management (List A #4, #11, #12, #15; List B #8, #9)

- [x] 6.1 Update `_classify_dir` and `hub.download()` in `libs/geomemory/src/geomemory/embeddings/hub.py` to filter vision models from text embedders and verify weights file presence before declaring a model downloaded/loadable.
- [x] 6.2 Update `server/src/geofront_api/routers/models.py` to accept arbitrary HuggingFace repository IDs for download and update `SettingsPage.tsx` with a free-text download input and query cache invalidation on "Scan Models".
- [x] 6.3 Update `UpdateSettingsRequest` in `server/src/geofront_api/schemas.py` and `WorkspaceSettings` in `libs/geomemory/src/geomemory/core/models.py` to accept `llm_context_window` up to 2,000,000, `embedding_provider`, and Cloudflare fields, verifying `PUT /api/v1/workspace/settings` accepts 256,000.
- [x] 6.4 Provide an option in workspace settings to persist runtime API keys to a local `.geofront/secrets.json` file excluded from version control so keys survive server restarts.

## 7. Farms Registry, Background Eval & UI Expansion (List A #9, #14; List B #10, #12, #15)

- [x] 7.1 Convert `POST /api/v1/eval/run` in `server/src/geofront_api/routers/eval.py` to a background job returning 202, and verify job status polling.
- [x] 7.2 Update `_find_farms_geojson()` in `server/src/geofront_api/routers/agent/farms.py` to search database-stored vector layers and match property aliases (`id`, `farm_id`, `FID`), and add a sample `sample/farms.geojson` with explicit `farm_id` attributes.
- [x] 7.3 Add expandable "Show more" / "Show less" text toggles on `SearchPage.tsx`, `AssetsPage.tsx`, and `AskPage.tsx` source drawers, and verify UI rendering.
