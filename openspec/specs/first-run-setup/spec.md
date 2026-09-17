# first-run-setup Specification

## Purpose
Guides a first-time user from a blank slate to a usable workspace: create a
new workspace (name only, path defaults to the platform root) or open an
existing one by path, and configure compute — offline/online mode, the LLM
provider and its base URL and key, and the embedding model with its
Hugging Face endpoint — before entering the app. All of these can be changed
later on the Settings page.

## Requirements

### Requirement: Setup wizard appears at login when no workspace is open
The app SHALL show a setup wizard (modal/overlay) on first run and whenever
the gateway reports the workspace closed, and SHALL NOT let the user dismiss
it without either creating or opening a workspace.

#### Scenario: Fresh load, no workspace
- **WHEN** the app loads and `GET /api/v1/workspace` returns `status: closed`
- **THEN** the setup wizard renders with two tabs: "Create new" and "Open existing"
- **AND** the rest of the app is not reachable until a workspace is open

#### Scenario: Wizard dismissed without action
- **WHEN** the user clicks outside or presses Escape with no workspace open
- **THEN** the wizard stays open (no dismissal); only Create or Open submits close it

### Requirement: Create-new path defaults to the platform root
The create-new tab SHALL require only a workspace name; when the path field
is left empty the workspace is created under the resolved default root
(`GEOFOND_WORKSPACE`, falling back to `./Workspaces`), i.e.
`<root>/<name>/`.

#### Scenario: Create with name only
- **WHEN** the user types only a name and submits
- **THEN** `POST /workspace/create` is sent with `path: ""` and `name: <name>`
- **AND** the resulting workspace lives at `<resolved-root>/<name>/`

#### Scenario: Create with explicit path
- **WHEN** the user types a path and a name
- **THEN** the workspace is created at `<path>/<name>/` (nested, per spec)

### Requirement: Open-existing accepts a parent directory
The open tab SHALL accept a path that is either the workspace directory itself
or a parent directory containing exactly one workspace; folder-picking
(webkitdirectory) and typed paths both work.

#### Scenario: Open by parent dir
- **WHEN** the user picks a folder that contains one workspace subdirectory
- **THEN** `POST /workspace/open` opens that workspace (200) without error

#### Scenario: Open unknown path
- **WHEN** the user submits a path with no workspace under it
- **THEN** the response is `404 workspace_not_found` and the wizard shows the error inline

### Requirement: Wizard configures offline/online mode
The wizard SHALL offer an explicit offline/online toggle for the workspace.
Online is the default and enables model downloads; offline disables them and
requires pre-cached models. The toggle is changeable later on the Settings
page and re-enables downloads when flipped back.

#### Scenario: Default is online
- **WHEN** the wizard opens with a fresh workspace
- **THEN** the offline toggle is off and download affordances are enabled

#### Scenario: Offline toggled on
- **WHEN** the user toggles offline on before creating
- **THEN** `POST /workspace/create` is sent with `offline: true` and download buttons are disabled in the wizard

### Requirement: Wizard configures the LLM provider, base URL, and key
The wizard SHALL surface the LLM provider (`api` remote OpenAI-compatible,
default; or `llamacpp` local GGUF), the API base URL, the model id, and the
API key. The key is applied server-side at runtime via
`PUT /workspace/settings` (`llm_api_key`) and is never persisted to the
workspace DB or returned. Defaults: provider `api`, base URL the gateway
default (OpenAI-compatible), model id `kilo-auto/free`.

#### Scenario: Provider default
- **WHEN** the wizard opens
- **THEN** the LLM provider field defaults to `api`, the base URL defaults to the
  Kilo gateway `https://api.kilo.ai/api/gateway/v1`, and the model id defaults
  to `kilo-auto/free` (all already the library defaults in
  `geomemory.qa.api_backend.default_kilo_base_url` and
  `WorkspaceSettings.llm_model_id`)

#### Scenario: Key submitted with create
- **WHEN** the user enters an API key and creates the workspace
- **THEN** the key is applied via `PUT /workspace/settings` (`llm_api_key`)
  immediately after create, before the app enters the main shell

#### Scenario: llamacpp selected
- **WHEN** the user switches the provider to `llamacpp`
- **THEN** the base URL field is hidden or deprioritized and a model path field is shown instead

### Requirement: Wizard configures the embedding model and its Hugging Face endpoint
The wizard SHALL surface the embedding backend (`onnx` default, plus
`sentence-transformers`, `llama-cpp`, `hashing`), the model id (default
`Xenova/all-MiniLM-L6-v2`), and the Hugging Face endpoint URL the downloads
are fetched from (default `https://huggingface.co`, overridable via
`HF_ENDPOINT`). Online mode downloads and caches the model on first use;
offline mode requires it to be pre-cached.

#### Scenario: Embedding defaults
- **WHEN** the wizard opens
- **THEN** the text embedding backend defaults to `onnx`, the text model id to
  `Xenova/all-MiniLM-L6-v2` (the canonical MiniLM quantized ONNX export, already
  the `WorkspaceSettings.onnx_model_name` default), and the HF endpoint to
  `https://huggingface.co`
- **AND** the vision embedding default is OLMoEarth Nano v1.2
  (`image.olmoearth-nano-v12.v1`, already the library default), downloaded on
  first use when online

#### Scenario: Online download
- **WHEN** the user is online and selects an uncached model
- **THEN** a "Download" affordance is available and the model is fetched from
  the configured HF endpoint and cached under `GEOMEMORY_EMBEDDING_ROOT` /
  `HF_HOME`

#### Scenario: Offline blocks download
- **WHEN** the user is offline and selects an uncached model
- **THEN** the download button is disabled and the hint "downloads require
  offline=false" shows

#### Scenario: HF endpoint override
- **WHEN** the user enters a custom HF endpoint URL
- **THEN** subsequent model downloads are fetched from that endpoint

### Requirement: Downloaded models are reusable across workspaces
The wizard SHALL let the user pick a shared model cache root (default
`~/.cache/huggingface`, overridable to any directory). Downloads SHALL land
there and SHALL be discoverable by every workspace opened afterwards — the
hub scans `GEOMEMORY_EMBEDDING_ROOT` first, so a model downloaded once is
cached once and reused, never re-downloaded per workspace.

#### Scenario: Model downloaded in one workspace is visible in another
- **WHEN** workspace A downloads `Xenova/all-MiniLM-L6-v2` to the shared root
- **THEN** workspace B's model list shows it as already downloaded and does
  not re-download it

#### Scenario: Shared root override
- **WHEN** the user sets the shared cache root to `./models`
- **THEN** subsequent downloads land under `./models/huggingface/hub/` and
  all workspaces scan that path

#### Scenario: Per-workspace path still works
- **WHEN** a workspace sets its own `embedding_path` to a directory
- **THEN** that path is scanned in addition to the shared root (hub roots
  order: `GEOMEMORY_EMBEDDING_ROOT` → `embedding_path` → dev root → home
  cache → workspace indexes), so nothing is lost

### Requirement: Workspace survives page refresh
The active workspace SHALL remain open after a page reload; the gateway
SHALL reopen the last active workspace on startup and the web app SHALL
reflect it on mount without requiring user action.

#### Scenario: Reload with open workspace
- **WHEN** the page reloads while a workspace is open
- **THEN** `GET /workspace` returns `status: open` with the same path
- **AND** the Overview page renders populated state, not the empty state

#### Scenario: Reload after close
- **WHEN** the page reloads after the user closed the workspace
- **THEN** `GET /workspace` returns `status: closed` and the setup wizard shows
