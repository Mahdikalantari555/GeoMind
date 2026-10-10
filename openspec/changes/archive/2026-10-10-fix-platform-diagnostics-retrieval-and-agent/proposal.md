# Proposal

## Why

Comprehensive end-to-end testing and deep code audits revealed 15 critical operational issues spanning user experience, diagnostics, LLM connectivity, retrieval indexing, agent orchestration, multilingual search, document chunking, and storage write safety:

1. **Doctor environment diagnostics**: Treats optional/uninitialized components (`indexes_dir`, Java 11+, Qdrant) as hard failures without distinguishing "not configured" from "broken".
2. **Doctor LLM probe**: Only checks env var existence without an active network probe to verify remote completions, latency, or auth status.
3. **Ask page failure masking**: Masks actual backend `abstention_reason` exception strings with generic configuration hints.
4. **Context window ceiling**: Hard ceiling of 200,000 tokens blocks 256k+ modern foundation models.
5. **Agent empty chat responses**: Emits blank bubbles when `response.content` is empty/null, lacking fallback messaging, raw LLM logging, and SSE error event propagation.
6. **Agent context engineering**: Lacks collection and asset context scoping in agent chat.
7. **Multilingual search**: ASCII-only FTS regex `[a-z0-9_]` drops RTL/Persian queries, yielding empty sparse results.
8. **Index strength & stats**: Rebuild UI lacks manifest statistics (vector count, dimension, latency, active space ID).
9. **Clamped text**: Search, Assets, and Ask source cards use static `line-clamp-4` without "Show more" toggles.
10. **Ingestion & page locators**: Multi-page PDF chunking assigns all segment locators to page 0; uppercase heuristics fragment on formulas/acronyms.
11. **Model classification & scan**: `hub._classify_dir` misclassifies vision checkpoints (e.g. OlmoEarth) as ST text models and flags tokenizer-only folders as loadable; "Scan Models" fails to invalidate React query caches.
12. **Free-text model download**: Hub download only works for locally discovered models, lacking HuggingFace repo ID direct inputs.
13. **Stale index space labels**: Rebuild endpoints and UI hardcode `text.nomic.v1` regardless of chosen backend or active settings.
14. **Farms registry**: Searches only local filesystem folders instead of database vector layers; crashes on empty geometries (`min(xs)`); strictly requires `farm_id`.
15. **Secret persistence & concurrency**: Keys reset on server restart; ingestion and eval jobs risk SQLite lock contention by bypassing `write_lock`; agent tools open duplicate unmanaged `GeoMemory` connections; Ask pipeline runs duplicate retrieval and premature stop sequences (`\n\n`).

Fixing these issues restores full operational integrity across GeoMemory, GeoAgent, GeoFront API, and the Web SPA.

## What Changes

- **Doctor diagnostics & LLM probe**: Distinguish unindexed state and optional tools in Doctor; add active completion probe (`GET /api/v1/doctor/llm?test=true`) with latency and status.
- **Ask QA pipeline & error display**: Surface real `abstention_reason` strings in the UI; eliminate redundant retrieval in `Workspace.ask()`; remove premature `\n\n` stop sequences in `ChatService.ask()`.
- **Dynamic index space resolution**: Dynamically resolve active vector space IDs from settings across API routes, UI, and `Workspace._dense_search()`, replacing hardcoded `text.nomic.v1`.
- **Agent runtime & context engineering**: Wire workspace LLM provider settings into `AgentService.init()`; support collection/asset context scoping; add non-empty fallback strings and SSE error events; protect `advisor_tools._feature_bbox` against empty geometries; reuse workspace instances in memory tools.
- **Multilingual search**: Add Unicode word pattern support to FTS extraction and fallback to dense-only retrieval for non-Latin queries.
- **Accurate PDF chunking**: Track per-page offsets in `PdfLoader` and map true page numbers in `HeaderThenTokenChunker`; refine header detection to prevent false splits on acronyms.
- **Model Hub management**: Add free-text HuggingFace repo ID downloads; filter vision models from text hub; verify weight file presence before declaring models downloaded; invalidate query caches on Scan Models.
- **Settings & context ceiling**: Raise context window ceiling to 2,000,000 in `WorkspaceSettings` and gateway schemas; support Cloudflare provider fields.
- **Concurrency & background jobs**: Convert `POST /api/v1/eval/run` to a 202 background job; enforce write lock acquisition during file ingestion; optionally allow local key persistence.
- **Farms registry & sample**: Query database vector layers; match property aliases (`id`, `farm_id`, `FID`); provide sample `farms.geojson`.
- **UI text expansion**: Add "Show more" toggles to line-clamped text in Search, Assets, and Ask drawers.

## Capabilities

### New Capabilities
- `retrieval-parity`: Correct vector space ID resolution for `sqlite-vec`, multilingual search handling, and accurate multi-page citation locators.
- `agent-runtime`: Propagation of workspace LLM settings to the agent core, context scoping, resilient GIS tool execution, and safe single-writer memory access.

### Modified Capabilities
- `gateway-server`: Active LLM network probe in Doctor, background eval jobs, dynamic index space parameters, relaxed schema validators, and optional secret persistence.
- `web-app`: Informative Doctor diagnostics, model download by HuggingFace ID, text expand toggles, manifest strength indicators, and agent context picker.
- `first-run-setup`: Increased LLM context window ceiling (up to 2,000,000 tokens) in workspace and gateway models.

## Impact

- `server/src/geofront_api/`: Routers for `doctor`, `index`, `ask`, `models`, `eval`, `workspace`, `agent`, and schemas updated.
- `libs/geomemory/`: `workspace.py`, `chat_service.py`, `index_service.py`, `hub.py`, `chunkers/header_then_token.py`, `loaders/pdf.py`, and `models.py` updated.
- `libs/geoagent/`: `agent.py`, `advisor_tools.py`, and `tools/memory_tools.py` updated.
- `apps/web/`: `DoctorPage.tsx`, `IndexPage.tsx`, `SettingsPage.tsx`, `SearchPage.tsx`, `AssetsPage.tsx`, `AskPage.tsx`, `AgentChatPage.tsx`, `FarmsPage.tsx`, and `api/` updated.
