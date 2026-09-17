# gateway-server Specification

## MODIFIED Requirements

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

### Requirement: Uniform error envelope
Every error response SHALL use `{ error: { code, message, detail? } }`.
`RequestValidationError` SHALL map to `422` with `code=validation`.

#### Scenario: Validation failure
- **WHEN** a request fails Pydantic validation
- **THEN** the response is `422` with `error.code == "validation"` and `error.detail` listing the failing fields

#### Scenario: 500 carries request_id
- **WHEN** an unhandled exception occurs
- **THEN** the response is 500 with `error.code=internal_error`, `error.detail.request_id` present, and header `X-Request-ID` matching `detail.request_id`, and server log contains the same id

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

### Requirement: Typed doctor diagnostics (no object-in-checks)
`GET /api/v1/doctor` SHALL return `{ environment, workspace: {ok, checks: Record<string, bool|string|number|null>}, workspace_open: {ok, checks: ...}, diagnostics: { llm, qdrant, pdf_parser, vision } }` where `checks` never contains nested objects. Rich diagnostics SHALL live only in `diagnostics`.

#### Scenario: Doctor checks are flat
- **WHEN** `GET /api/v1/doctor` is fetched
- **THEN** every value in `workspace.checks` and `workspace_open.checks` is `boolean | string | number | null`, and `diagnostics.llm.provider` etc are typed objects

#### Scenario: LLM probe flat
- **WHEN** `GET /api/v1/doctor/llm` is fetched
- **THEN** it returns `{ provider, key_env, key_configured, base_url, model_id, context_window }` with primitives only

## ADDED Requirements

### Requirement: Settings validation accepts canonical backends
`PUT /api/v1/workspace/settings` SHALL accept `vector_backend` values
`sqlite-vec`, `lancedb`, `qdrant`, `numpy` (and migrate `local` → `lancedb`).
`sqlite-vec` SHALL be the default vector backend for newly created workspaces;
`lancedb` and `qdrant` remain available as opt-in backends and are never
required. Creating a workspace SHALL default `offline` to `false`.

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

## REMOVED Requirements

### Requirement: Qdrant docker service
**Reason**: The Qdrant server image (~200 MB) is not needed for the default
stack — `sqlite-vec` is the default backend and Qdrant remains an opt-in
backend reachable by setting `vector_backend=qdrant` + `qdrant_url` against a
Qdrant instance the operator runs themselves. Removing the service shrinks
the gateway image and removes a hard external dependency from the default
compose. No library code, settings, tests, or UI is affected.

**Migration**: If you want Qdrant, run `qdrant/qdrant` separately and set
`GEOMEMORY_QDRANT_URL` (or `qdrant_url` in workspace settings). The gateway
imports `qdrant_client` lazily and never requires it.