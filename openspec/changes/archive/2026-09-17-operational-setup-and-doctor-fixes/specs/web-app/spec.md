# web-app Specification

## MODIFIED Requirements

### Requirement: Workspace default UX
The workspace switcher SHALL offer `Workspaces` (resolved `GEOFOND_WORKSPACE`)
as default, auto-create it, and display the resolved absolute path. Closing/no
workspace SHALL show "No workspace open" with create/open affordance. When no
workspace is open the app SHALL show a setup wizard (create/open + LLM key +
base URL + embedding model) instead of the main shell, and the wizard SHALL
accept a parent directory path as well as the exact workspace path.

#### Scenario: First run no workspace
- **WHEN** the app loads with no workspace open
- **THEN** the header pill shows "workspace: closed" and the Overview empty state offers "Create in default Workspaces/"

#### Scenario: Setup wizard on closed workspace
- **WHEN** the app loads and `GET /api/v1/workspace` returns `status: closed`
- **THEN** the setup wizard renders with Create-new and Open-existing tabs
- **AND** the main shell is not reachable until a workspace is open

#### Scenario: Wizard exposes compute config
- **WHEN** the setup wizard opens
- **THEN** it shows an offline/online toggle (online default), an LLM
  provider selector (`api` default, `llamacpp`), an LLM base URL field, an
  LLM model id field, an LLM API key field, an embedding backend selector
  (`onnx` default), an embedding model id field, and a Hugging Face
  endpoint URL field (default `https://huggingface.co`)
- **AND** all of these are editable later on the Settings page

#### Scenario: Open by parent directory
- **WHEN** the user picks or types a folder that contains exactly one workspace
- **THEN** `POST /workspace/open` opens that workspace (200) without error

#### Scenario: Reload preserves open workspace
- **WHEN** the page reloads while a workspace is open
- **THEN** `GET /workspace` returns `status: open` with the same path and the Overview renders populated state

### Requirement: Doctor rendering without [object Object]
Doctor SHALL render `checks` as flat rows (boolean→badge, string/number→mono
text) and render `diagnostics.{llm,qdrant,pdf_parser,vision}` in dedicated
sections with typed fields, never calling `String(object)`. It SHALL additionally
report optional-dependency status (Pillow, PyMuPDF, opendataloader-pdf,
python-docx, rasterio, shapely, geopandas, sqlite-vec, onnxruntime,
huggingface_hub) and SHALL NOT render GGUF model-path fields
(LLM/Embedding/Vision GGUF path) or the "Downloads require offline=false"
hint when online. Qdrant SHALL be reported as an optional backend, not a
requirement.

#### Scenario: No object string
- **WHEN** Doctor is viewed with a workspace open
- **THEN** the DOM contains no text "`[object Object]`" and the diagnostics sections show `provider`, `model_id`, `key_configured`, `qdrant.reachable`, `pdf_parser.resolved`, `vision.checkpoint_exists` as primitives/badges

#### Scenario: Deps reported
- **WHEN** Doctor is viewed
- **THEN** the optional-dependency list reflects the runtime environment and Pillow/PyMuPDF/python-docx show installed

#### Scenario: No GGUF path fields
- **WHEN** Doctor or Settings is viewed
- **THEN** the DOM contains no "GGUF path" labels and no offline hint when `offline` is false

## ADDED Requirements

### Requirement: Settings Save works for canonical backends
`PUT /workspace/settings` SHALL accept `vector_backend: "sqlite-vec"` (the
canonical default) in addition to `qdrant`/`lancedb`/`numpy`; saving unchanged
defaults from the Settings page SHALL return 200, never `422`.

#### Scenario: Save with sqlite-vec
- **WHEN** the Settings page saves with `vector_backend: "sqlite-vec"`
- **THEN** the request is `200`, not `422`

#### Scenario: Save with qdrant
- **WHEN** the Settings page saves with `vector_backend: "qdrant"`
- **THEN** the request is `200`, not `422`

### Requirement: Online-first defaults and honest offline messaging
Creating a workspace SHALL default `offline` to `false`. Download affordances
SHALL be enabled and no offline hint shown when `offline` is false; when
`offline` is true downloads are disabled and the hint shows.

#### Scenario: Default offline flag
- **WHEN** a workspace is created with no explicit flag
- **THEN** `settings.offline` is `false`

#### Scenario: Offline hint visibility
- **WHEN** `offline` is `false`
- **THEN** download buttons are enabled and no offline hint shows
- **WHEN** `offline` is `true`
- **THEN** download buttons are disabled and the offline hint shows

### Requirement: Full web test coverage
The web app SHALL have a runnable test suite (Vitest unit + Playwright E2E
with screenshots) that verifies the setup wizard, workspace lifecycle,
settings save, doctor rendering, ingest/search/ask flow, RTL flip, and
empty/loading/error states against a live gateway.

#### Scenario: E2E smoke with screenshots
- **WHEN** the Playwright suite runs
- **THEN** it opens the app, captures a screenshot at each major step (wizard, overview, settings save, doctor, ingest, search, ask), and asserts no `[object Object]`, no 422 on save, and correct empty states