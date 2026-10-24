# gateway-server Specification

## Purpose
TBD - created by archiving change add-gateway-server. Update Purpose after archive.

## Requirements

### Requirement: HTTP facade over public libraries
The server SHALL expose `/api/v1` endpoints that call only the public facades of `geomemory` and `geoagent`, and SHALL NOT import any library internal module, and its transitive graph SHALL NOT contain `txtai`, `torch`, `torchvision`, `torchaudio`, `sentence-transformers`, `accelerate`, or `safetensors` when installed without `[vision]`; it SHALL satisfy this via `pipdeptree` in CI.

#### Scenario: Facade-only imports
- **WHEN** the server package is inspected for imports
- **THEN** every `geomemory`/`geoagent` import resolves to a public API path

#### Scenario: No torch in gateway env
- **WHEN** `pip install geofront-api` (or `server` deps) is performed in a clean env
- **THEN** `pipdeptree | grep -qiE "torch|txtai"` finds no matches

### Requirement: Workspace state machine
The server SHALL hold at most one active workspace (create/open/close),
serialize write operations behind an async lock, and run as a single worker.
Requests requiring a workspace SHALL fail with `409 workspace_not_open`
when none is active. `GET /api/v1/doctor` and `GET /api/v1/doctor/llm` are
exceptions: they are environment diagnostics and SHALL return `200` with a
`closed` status (or gateway LLM defaults) instead of `409`.

#### Scenario: Search without workspace
- **WHEN** `POST /api/v1/search` is called and no workspace is open
- **THEN** the response is `409` with the error envelope

#### Scenario: Active workspace persists across restart
- **WHEN** the gateway restarts while a workspace was open
- **THEN** `GET /api/v1/workspace` returns `status: open` with the same path
- **AND** the workspace is reopened transparently (no client action required)

#### Scenario: Restart after close
- **WHEN** the gateway restarts after the workspace was closed
- **THEN** `GET /api/v1/workspace` returns `status: closed`

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

### Requirement: SSE event stream
The server SHALL stream `asset_created`, `collection_created`, and job
progress events over `GET /api/v1/events` for UI cache invalidation.

#### Scenario: Event after ingest
- **WHEN** an ingest job completes
- **THEN** an `asset_created` event is emitted on the SSE stream

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

### Requirement: Sandboxed artifact serving
`GET /api/v1/agent/files/*` SHALL serve only files under the active workspace's `runs/` directory, normalizing paths and rejecting traversal. Errors SHALL use the uniform envelope (404 `asset_not_found` / `not_found`) with `X-Request-ID`.

#### Scenario: Traversal rejected
- **WHEN** a request path contains `..` or escapes the runs root
- **THEN** the response is `404`

### Requirement: Uniform error envelope
Every error response SHALL use `{ error: { code, message, detail? } }`.
`RequestValidationError` SHALL map to `422` with `code=validation`.

#### Scenario: Validation failure
- **WHEN** a request fails Pydantic validation
- **THEN** the response is `422` with `error.code == "validation"` and `error.detail` listing the failing fields

#### Scenario: 500 carries request_id
- **WHEN** an unhandled exception occurs
- **THEN** the response is 500 with `error.code=internal_error`, `error.detail.request_id` present, and header `X-Request-ID` matching `detail.request_id`, and server log contains the same id

### Requirement: Doctor reflects lightweight stack
`GET /api/v1/doctor` diagnostics SHALL report `embedding_provider` (active
provider, space_id, dimension) and `sqlite_vec` (`installed`, `loadable`,
`version`) alongside existing LLM/Qdrant/Vision checks, and SHALL surface
optional-dependency status for the document/image stack (Pillow, PyMuPDF,
opendataloader-pdf, python-docx, rasterio, shapely, geopandas) as reported by
the runtime environment. Qdrant SHALL be optional and reported, never
required.

#### Scenario: Doctor after refactor
- **WHEN** `GET /api/v1/doctor` is called with `sqlite-vec` installed
- **THEN** response contains `diagnostics.sqlite_vec.loadable == true` and `diagnostics.embedding.active_provider == "onnx"` and no `txtai` key

#### Scenario: Optional deps reported
- **WHEN** `GET /api/v1/doctor` is called
- **THEN** `environment.optional_deps` contains entries for Pillow/PyMuPDF/python-docx reflecting the runtime env

#### Scenario: Qdrant optional, not blocking
- **WHEN** `GET /api/v1/doctor` is called and Qdrant is unreachable
- **THEN** the response is `200` and `diagnostics.qdrant.reachable` is `false` (or absent), never a non-2xx

### Requirement: Workspace default root and path normalization
The system SHALL default the workspace root to the gitignored `Workspaces`
directory and SHALL auto-create parent directories on create. Opening a
workspace by its parent directory (a folder containing exactly one workspace)
SHALL succeed.

#### Scenario: Create with empty path uses default
- **WHEN** `POST /api/v1/workspace/create` is called with `path=""` or omitted
- **THEN** the workspace is created under `GEOFOND_WORKSPACE/<name>/` and response `path` equals that resolved path

#### Scenario: Gitignore covers canonical dir
- **WHEN** `.gitignore` is inspected
- **THEN** it contains `Workspaces/` (and not just variants) so `Workspaces/**` is never committed

#### Scenario: Open by parent directory
- **WHEN** `POST /api/v1/workspace/open` is called with the path of a folder containing one workspace
- **THEN** the response is `200` with `status: open` and the resolved workspace path

### Requirement: List existing workspaces (suggestions)
`GET /api/v1/workspace/suggestions` SHALL return existing workspaces under the
default workspace root so the UI can suggest them and prefill the open path.
A directory counts as a workspace if it contains the `.geomemory` marker file
(or a `geomemory.db`). Workspaces may live directly under the root or nested one
level deep (as created by `POST /workspace/create`, which nests at
`<root>/<path>/<name>/`). The response includes the resolved `root` so the web
client can prefill the open-tab path with the default `Workspaces/` folder.

#### Scenario: Suggestions when no workspaces exist
- **WHEN** `GET /workspace/suggestions` is called and the default root contains no workspaces
- **THEN** the response is `200` with `suggestions: []` and the resolved `root`

#### Scenario: Suggestions lists real workspaces
- **WHEN** two workspaces exist under the default root and one directory is not a workspace
- **THEN** the response is `200` and `suggestions` contains exactly the two workspace paths (resolved), ignoring non-workspace directories

### Requirement: Typed doctor diagnostics (no object-in-checks)
`GET /api/v1/doctor` SHALL return `{ environment, workspace: {ok, checks: Record<string, bool|string|number|null>}, workspace_open: {ok, checks: ...}, diagnostics: { llm, qdrant, pdf_parser, vision } }` where `checks` never contains nested objects. Rich diagnostics SHALL live only in `diagnostics`.

#### Scenario: Doctor checks are flat
- **WHEN** `GET /api/v1/doctor` is fetched
- **THEN** every value in `workspace.checks` and `workspace_open.checks` is `boolean | string | number | null`, and `diagnostics.llm.provider` etc are typed objects

#### Scenario: LLM probe flat
- **WHEN** `GET /api/v1/doctor/llm` is fetched
- **THEN** it returns `{ provider, key_env, key_configured, base_url, model_id, context_window }` with primitives only

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

### Requirement: Dynamic default workspace root
The gateway SHALL dynamically resolve the default workspace root to `<project_root>/Workspaces` in development environments and `/workspace` in container environments, overridable by `GEOFOND_WORKSPACE`. It SHALL NOT depend on hardcoded machine-specific paths.

#### Scenario: Workspace creation with empty path
- **WHEN** `POST /api/v1/workspace/create` is requested with an empty or omitted path
- **THEN** the workspace directory is created under the dynamically resolved project root `Workspaces/` directory without permission errors or hardcoded path failures

### Requirement: Robust ingestion request validation
The gateway SHALL accept multipart file uploads for `POST /api/v1/ingest` and JSON payloads for `POST /api/v1/ingest/bytes`, returning clear 422 error structures with specific field names when required attributes (`file`, `collection_id`) are missing.

#### Scenario: Missing collection id
- **WHEN** a client submits a file upload to `POST /api/v1/ingest` without `collection_id`
- **THEN** the gateway returns `422 Unprocessable Entity` with a descriptive validation error identifying `collection_id`

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
