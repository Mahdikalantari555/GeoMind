## Why

The app is functionally complete but is not yet *usable end-to-end* in a real
session: there is no first-run setup, the workspace switcher rejects the
common case of pointing at a parent directory, `Save` on Settings always
fails with `422 Request validation failed` because `vector_backend` rejects
`sqlite-vec`, the Doctor page advertises offline mode and GGUF model paths
that the platform no longer uses, and the web test harness has never been
run. This change makes the project actually operable: a guided setup on
login, honest online-first defaults, a working settings save, a Doctor page
that reports the real environment, and a verified web test suite.

## What Changes

- **New: first-run setup wizard.** A modal shown at login when no workspace is
  open. It offers two paths — *Create new* (name only; path defaults to
  `./Workspaces/<name>`) and *Open existing* (path typed or folder-picked).
  The wizard also configures compute: offline/online toggle (online default),
  LLM provider (`api` default, `llamacpp`), LLM base URL (default Kilo
  `https://api.kilo.ai/api/gateway/v1`), LLM model id (default
  `kilo-auto/free`), LLM API key, embedding backend (`onnx` default),
  text embedding model id (default `Xenova/all-MiniLM-L6-v2`), vision
  embedding (default OLMoEarth Nano v1.2, downloaded on first use), and the
  Hugging Face endpoint URL (default `https://huggingface.co`). Every field
  is re-editable on the Settings page later.
- **Workspace switcher accepts a parent path.** Typing or folder-picking a
  directory that *contains* exactly one workspace now opens that workspace
  instead of demanding the exact nested `path/name` path. Browsing still
  uploads a folder (webkitdirectory); typing a path now also works.
- **Workspace survives page refresh.** The active workspace is no longer lost
  on reload — the gateway persists the active workspace path in its state
  and reopens it on startup; the web app re-reads it on mount.
- **Settings `Save` works.** `UpdateSettingsRequest.vector_backend` pattern
  is corrected to include `sqlite-vec` (the canonical default).
- **Defaults are online-first.** `CreateWorkspaceRequest.offline` defaults to
  `false`; the Doctor/Settings surfaces show online as the normal state and
  only warn when offline blocks downloads.
- **Doctor page cleaned up.** Removed/hidden: `Model Paths` (LLM GGUF /
  Embedding GGUF / Vision GGUF path) section and the `Vision GGUF path` field,
  and the misleading "Downloads require offline=false" hints when online.
  Added: optional-dependency status for Pillow, PyMuPDF, opendataloader-pdf,
  python-docx (they are installed in the `geospatial` env — the Doctor was
  reporting them as absent because it probed the gateway's own env, not the
  conda env the services actually run in).
- **Vector backends: sqlite-vec is the default; lancedb and qdrant stay
  optional.** Qdrant is **NOT** removed — deleting it would break
  `geomemory.index.qdrant_backend`, its unit/integration tests,
  `WorkspaceSettings.qdrant_url`/`qdrant_api_key`, the
  `index_service` dispatch, `doctor_qdrant`, the `qdrant` docker service,
  and the Settings UI fields. Instead this change makes the default
  `sqlite-vec` explicit everywhere, keeps `lancedb`/`qdrant` as opt-in
  backends, and ensures the gateway and web never hard-require either.
- **Web test harness made operational.** Vitest + Playwright E2E (with
  screenshots at each major step) wired to a runnable gateway
  (docker-compose) so the full web can actually be tested.

## Capabilities

### New Capabilities
- `first-run-setup`: guided onboarding modal (create/open + LLM key + base
  URL + embedding model selection) surfaced at login.

### Modified Capabilities
- `web-app`: workspace switcher path semantics, settings save, Doctor
  content, online-first defaults, refresh persistence, vector-backend
  selector (default sqlite-vec; lancedb/qdrant optional).
- `gateway-server`: workspace state persistence across restarts, `vector_backend`
  validation, optional-dependency diagnostics sourced from the runtime env,
  vector-backend defaulting.

## Impact

- `server/src/geofront_api/schemas.py` — `CreateWorkspaceRequest.offline`,
  `UpdateSettingsRequest.vector_backend` pattern.
- `server/src/geofront_api/state.py` — persist + reopen active workspace.
- `server/src/geofront_api/routers/doctor.py` — env-sourced optional deps,
  Qdrant optional, online-first messaging.
- `libs/geomemory/src/geomemory/core/models.py` — `vector_backend` default
  stays `sqlite-vec`; qdrant fields remain (optional).
- `apps/web/src/features/workspace/` — `WorkspaceSwitcher`, `SetupModal`,
  `SettingsPage` (model-path section removed, backend selector added),
  `OverviewPage`.
- `apps/web/src/features/doctor/DoctorPage.tsx` — hide GGUF paths, show deps.
- `apps/web` — vitest + playwright test wiring, i18n keys.
- `docker-compose.yml` — runnable gateway for web tests (qdrant service
  unchanged, still optional).