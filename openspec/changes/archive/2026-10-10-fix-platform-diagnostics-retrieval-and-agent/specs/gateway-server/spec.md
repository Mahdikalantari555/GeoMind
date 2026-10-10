# Spec Delta: gateway-server

## MODIFIED Requirements

### Requirement: Background jobs
Long operations (ingest, index build/rebuild, benchmark, playbook runs) SHALL return `202 {job_id}` and report progress via `GET /api/v1/jobs/{id}` until terminal status; job results SHALL surface library outcomes including ingest dedup (`skipped: true`). File ingestion workers SHALL acquire the gateway write lock during database mutations. On failure the job SHALL set `error` and `job_progress` SHALL emit an `error` status that polling `GET /api/v1/jobs/{id}` surfaces.

#### Scenario: Ingest job lifecycle
- **WHEN** a file is uploaded to `POST /api/v1/ingest`
- **THEN** the response is `202` with a job id
- **AND** polling `GET /jobs/{id}` transitions queued → running → done with the ingest result (asset_id, segment_count, or skipped flag)

#### Scenario: Failed ingest surfaced
- **WHEN** `ws.ingest` raises inside a job
- **THEN** `GET /jobs/{id}` eventually reports `status=error` with `error.code` and `detail`, and an SSE `job_progress` event with `status=error` is published

#### Scenario: Benchmark evaluation job lifecycle
- **WHEN** `POST /api/v1/eval/run` is submitted
- **THEN** the server returns `202` with a `job_id` and executes evaluation in the background without blocking the write lock synchronously

### Requirement: Hybrid LLM compute, secrets handling
The server SHALL default LLM selection to the API provider
(OpenAI-compatible), support `llamacpp` as local fallback, and read API keys
from server environment variables (name from `llm_api_key_env`, default
`GEOMEMORY_LLM_API_KEY`). The API key MAY be set via `PUT /api/v1/workspace/settings` field `llm_api_key`; when provided the gateway SHALL set `os.environ[effective_key_env]` at runtime (never persisted to the workspace DB) and SHALL never return the key value in any response. The env var name `llm_api_key_env` MAY be updated via settings. Unavailable backends SHALL produce `503` errors or library abstention results with explicit error details, never stack traces. The gateway SHALL seed `llm_api_base_url` and `llm_model_id` from the server env (`GEOMEMORY_LLM_API_BASE_URL` / `GEOMEMORY_LLM_MODEL_ID`) when a workspace is created or opened, so a deployment can configure the LLM connection without editing stored settings. The gateway SHALL provide an active network probe endpoint `GET /api/v1/doctor/llm/test` or probe parameters in `GET /api/v1/doctor/llm` that issue a lightweight chat completion request and report connectivity, latency, and error detail.

#### Scenario: Key never crosses the wire
- **WHEN** any endpoint's response payload is inspected
- **THEN** the API key value does not appear

#### Scenario: Key settable through settings
- **WHEN** `PUT /api/v1/workspace/settings` receives a body containing `llm_api_key`
- **THEN** the server sets the env var named by `llm_api_key_env` (or `GEOMEMORY_LLM_API_KEY` by default) to that value at runtime, does not persist the key to the workspace DB, and returns `200` with updated settings that do not contain the key

#### Scenario: LLM probe
- **WHEN** `GET /api/v1/doctor/llm` is called
- **THEN** it reports provider, key configured (bool), base URL, model id,
  and context window without leaking the key, and works without an open
  workspace (falling back to gateway defaults)

#### Scenario: LLM active network test
- **WHEN** `GET /api/v1/doctor/llm?test=true` is called
- **THEN** it issues a minimal chat completion request to the configured gateway and reports `reachable: true/false`, latency in milliseconds, and status or error detail

### Requirement: Settings validation accepts canonical backends
`PUT /api/v1/workspace/settings` SHALL accept `vector_backend` values
`sqlite-vec`, `lancedb`, `qdrant`, `numpy` (and migrate `local` → `lancedb`).
`sqlite-vec` SHALL be the default vector backend for newly created workspaces;
`lancedb` and `qdrant` remain available as opt-in backends and are never
required. Creating a workspace SHALL default `offline` to `false`. The endpoint SHALL also accept `embedding_provider` values (`onnx`, `cloudflare`, `hashing`, `llama-cpp`) and Cloudflare account and model fields, and SHALL accept `llm_context_window` values up to 2,000,000.

#### Scenario: Save sqlite-vec
- **WHEN** `PUT /workspace/settings` is sent with `vector_backend: "sqlite-vec"`
- **THEN** the response is `200`, not `422`

#### Scenario: Save qdrant (optional)
- **WHEN** `PUT /workspace/settings` is sent with `vector_backend: "qdrant"`
- **THEN** the response is `200`, not `422`

#### Scenario: Create defaults to online
- **WHEN** `POST /workspace/create` is sent without `offline`
- **THEN** `settings.offline` in the response is `false`

#### Scenario: Create defaults to sqlite-vec
- **WHEN** `POST /workspace/create` is sent without `vector_backend`
- **THEN** `settings.vector_backend` in the response is `"sqlite-vec"`

#### Scenario: Save cloudflare provider settings
- **WHEN** `PUT /workspace/settings` is sent with `embedding_provider: "cloudflare"`, `cloudflare_account_id`, and `cloudflare_model_id`
- **THEN** the response is `200` and saves the configuration

#### Scenario: Save large context window
- **WHEN** `PUT /workspace/settings` is sent with `llm_context_window: 256000`
- **THEN** the response is `200` and updates the context window

## ADDED Requirements

### Requirement: Index build resolves active space by default
`POST /api/v1/index/build` and `POST /api/v1/index/rebuild` SHALL resolve `space_id` from the workspace's active embedding settings when `space_id` is omitted or left as default. The server SHALL expose `GET /api/v1/index/manifest` returning index metadata (space ID, vector count, dimension, timestamp).

#### Scenario: Build index without explicit space_id
- **WHEN** `POST /api/v1/index/build` is called without query parameter
- **THEN** the gateway builds the index for the workspace's active embedding space rather than hardcoding `text.nomic.v1`

#### Scenario: Query index manifest
- **WHEN** `GET /api/v1/index/manifest` is called
- **THEN** the response includes active space ID, vector count, and vector dimension

### Requirement: Full-text answer generation without premature stop truncation
The grounded QA endpoint `POST /api/v1/ask` SHALL execute a single retrieval pass and SHALL NOT pass paragraph break stop sequences (`\n\n`) to remote LLM completion backends.

#### Scenario: Multi-paragraph response generation
- **WHEN** a user asks a question whose generated answer contains multiple paragraphs or list items
- **THEN** the model output is not truncated at the first double-newline and the complete answer is returned

### Requirement: Model download by arbitrary repo ID
`POST /api/v1/models/download` SHALL accept any valid HuggingFace model repo ID and backend (`onnx` or `st`) and trigger a background download job even if the model was not previously listed by local scan.

#### Scenario: Download unlisted HuggingFace model
- **WHEN** `POST /api/v1/models/download` is requested with an arbitrary HuggingFace repository ID
- **THEN** the gateway submits a background download job and returns `202`

### Requirement: Scoped agent chat endpoint
`POST /api/v1/agent/chat` SHALL accept optional `context_scope` (collections, assets) and stream SSE events including agent tool progress, messages, and structured errors.

#### Scenario: Chat with selected collections
- **WHEN** a chat request includes `context_scope: {"collections": ["col_water_stress"]}`
- **THEN** the agent loop prioritizes assets in that collection when formulating responses
