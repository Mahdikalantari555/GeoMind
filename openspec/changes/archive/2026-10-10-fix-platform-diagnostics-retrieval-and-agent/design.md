# Design

## Context

The GeoFoundation monorepo connects `geomemory` (memory & search engine), `geoagent` (autonomous tool-calling agent), `server` (FastAPI gateway), and `apps/web` (React SPA). See `proposal.md` for problem background and symptoms.

## Goals / Non-Goals

**Goals:**
- Provide true network reachability diagnostics for configured LLM gateways and eliminate false red alarms in Doctor checks.
- Ensure dense search and index building dynamically resolve and use the active vector space ID (`sqlite-vec` or hashing).
- Enable full multi-paragraph answers without premature cutoffs in Ask QA, and surface exact abstention error strings in the UI.
- Synchronize agent LLM configuration with workspace settings, support collection/asset context scoping, provide fallback responses, and protect against geometry exceptions and duplicate database connections.
- Provide multilingual retrieval for non-Latin queries (e.g., Persian).
- Preserve accurate page citation numbers in PDF chunking and avoid section fragmentation on uppercase acronyms.
- Allow downloading arbitrary HuggingFace models from the UI with proper cache refetching, and validate weight file presence.
- Add text expansion toggles across search and asset views, and display index manifest health statistics.
- Ensure background eval runs do not block the gateway, and file ingestion executes under the SQLite write lock.
- Support flexible farm registry property matching and sample data generation.

**Non-Goals:**
- Implementing a full external vector database deployment (SQLite and `sqlite-vec` remain default).
- Replacing the OpenDataLoader Java dependency (PyMuPDF fallback remains primary when Java is missing).
- Rewriting the entire agent tool catalog.

## Decisions

### 1. Active LLM Network Probe & Doctor Diagnostic Separation
- **Decision**: Extend `GET /api/v1/doctor/llm` with an optional query parameter `test=true` that sends a minimal chat request (`messages=[{"role": "user", "content": "ping"}]`, `max_tokens=1`, 5s timeout) via the stdlib HTTP client. In `DoctorPage.tsx`, map uncreated `indexes_dir` and missing optional Java/Qdrant to neutral/informational status badges rather than critical failures.
- **Alternatives considered**:
  - Pinging base URL root: rejected because OpenAI-compatible APIs return 404 or 405 on `GET /` or `GET /v1`.
  - Calling probe on every doctor poll: rejected to prevent slowing down dashboard polling.

### 2. Space ID Dynamic Resolution in Retrieval
- **Decision**: In `Workspace._dense_search()`, resolve `space_id` dynamically using the workspace's active embedder (`EmbeddingModelHub.summary(active_backend, active_model)["active_space_id"]`) instead of hardcoding `text.hash.v1`. In `server/routers/index.py` and web API clients, default `space_id` to `None` and resolve from `ws.settings`. Expose `GET /api/v1/index/manifest` to provide manifest statistics.
- **Alternatives considered**:
  - Forcing the user to supply `space_id` manually in every search and build call: rejected because workspace settings already specify the active provider and model.

### 3. QA Generation, Error Surfacing, and Single Retrieval Pass
- **Decision**: In `ChatService.ask()`, remove `\n\n` from `stop_sequences` in `GenerationRequest`. In `Workspace.ask()`, eliminate the redundant `self.search()` call prior to calling `chat.ask()`. In `AskPage.tsx`, display `result.abstention_reason` directly in the UI instead of a generic configuration message.
- **Alternatives considered**:
  - Dynamic stop sequences from client: rejected because grounded answers naturally contain multi-paragraph explanations and lists.

### 4. Agent Service Setting Synchronization, Context Scoping, and Concurrency
- **Decision**: In `AgentService.init()`, populate `AgentSettings.provider` fields (`base_url`, `model`, `api_key_env`, `api_key`) directly from `ws.settings`. In `AgentCore.chat()`, accept `context_scope` (collections, assets) and format them into the conversation context; return fallback text ("The model returned an empty response") when `response.content` is empty with no tool calls; emit SSE `error` events on exceptions. In `memory_tools`, reuse the server workspace instance instead of opening unmanaged duplicate SQLite connections.
- **Alternatives considered**:
  - Requiring separate `agent.yaml` configuration: rejected because user manages compute in workspace settings.

### 5. Multilingual and Non-ASCII FTS Extraction
- **Decision**: Update `_FTS_TERM_RE` to use Unicode word patterns `\w+`. If a query contains non-ASCII characters that SQLite FTS5 `unicode61` tokenizer cannot index, execute hybrid search by falling back to dense-only retrieval without letting an empty sparse set suppress results.
- **Alternatives considered**:
  - Installing a custom SQLite Persian tokenizer C extension: rejected because GeoMemory maintains an in-process, zero-external-system dependency model.

### 6. Accurate PDF Page Locators and Header Splitting
- **Decision**: In `PdfLoader`, retain per-page text offsets. In `HeaderThenTokenChunker`, match chunk character spans against page offsets so each chunk receives its real page locator. In `_is_header`, require line breaks before and after and exclude common formula symbols and acronyms.
- **Alternatives considered**:
  - Forcing OpenDataLoader for all PDFs: rejected because OpenDataLoader requires Java 11+, which is optional in local environments.

### 7. Model Hub Classification, Weight Validation, and Free-Text Entry
- **Decision**: In `hub._classify_dir`, exclude vision models (such as OlmoEarth) from sentence-transformers listings, and check for the presence of actual model weights (`.bin`, `.safetensors`, `.onnx`) before declaring a model downloaded or loadable. In `SettingsPage` and `IndexPage`, add a text input for free-form HuggingFace repository IDs and ensure `refetchModels()` invalidates the query cache.
- **Alternatives considered**:
  - Hardcoding a static list of models: rejected because remote sensing workflows require specialized foundation models.

### 8. Text Clamp UI Toggle & Index Strength Display
- **Decision**: Replace static `line-clamp-4` / `line-clamp-6` in `SearchPage`, `AssetsPage`, and `AskPage` drawer with an expandable text component. In `IndexPage`, fetch and render manifest statistics (vector count, dimension, latency, space ID).

### 9. Asynchronous Evaluation & Write Lock Safety
- **Decision**: Convert `POST /api/v1/eval/run` to a 202 background job using `JobManager.submit()`. Enforce `AppState.write_lock` acquisition in file ingestion background workers.
- **Alternatives considered**:
  - Running eval synchronously in a worker thread: rejected because it holds the SQLite write lock and blocks the entire server.

### 10. Farms Registry Database Discovery & Geometry Safety
- **Decision**: Update `_find_farms_geojson()` to search database vector assets in addition to workspace directories, and match property aliases (`id`, `farm_id`, `FID`, `FarmID`). Guard `_feature_bbox` against empty coordinate sequences. Provide a standard sample `farms.geojson`.

## Risks / Trade-offs

- **[Risk]** Active LLM probe may encounter network timeouts on slow connections.
  → *Mitigation*: Hard timeout of 5 seconds with graceful `reachable: false` and error message reporting.
- **[Risk]** Relaxing FTS regex to Unicode might match punctuation in RTL scripts.
  → *Mitigation*: Use regex word boundaries and sanitize FTS query strings with parameterization.
- **[Risk]** Background evaluation jobs might execute concurrently with ingestion.
  → *Mitigation*: All long-running mutation jobs acquire `AppState.write_lock` sequentially.
