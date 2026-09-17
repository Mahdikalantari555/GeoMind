# Design

## Context

See proposal.md for motivation. The app works but is not usable in a real
session: no first-run setup, the switcher rejects parent paths, Settings
Save always 422s, Doctor advertises offline/GGUF, and the web has never been
tested against a live gateway.

## Goals / Non-Goals

**Goals:** guided setup on login, parent-path open, settings save works,
online-first defaults, honest Doctor, workspace survives refresh, runnable
web tests, smaller docker image.

**Non-Goals:** new retrieval/agent/geo features; multi-workspace; remote sync;
making the gateway a reusable WebGIS engine (deferred — see Out of scope).

## Decisions

1. **Setup wizard = route-level overlay, not a separate page.** Rendered by
   AppShell when `GET /workspace` is closed; the router Outlet is replaced
   by the wizard. Keeps one entry point and one i18n namespace.
2. **Workspace persistence = server-side state file.** The gateway writes
   the active workspace path to `<root>/.geofront/active_workspace` on
   create/open/close and reopens it in the lifespan startup. The web needs
   no change beyond re-reading `GET /workspace` on mount. Chosen over
   localStorage because it survives a gateway restart and a different
   browser.
3. **Parent-path open = server-side.** `_open_workspace_path` already tries
   single-child directories; the wizard just needs to stop treating
   folder-pick as upload-only and to accept typed paths. No client logic.
3b. **Wizard compute fields map onto existing settings — no schema change.**
   offline → `offline`, llm_provider → `llm_provider`, llm_api_base_url →
   `llm_api_base_url`, llm_model_id → `llm_model_id`, llm_api_key →
   `llm_api_key` (runtime env, never persisted), embedding_backend →
   `embedding_backend`, onnx_model_name → `onnx_model_name`. The Hugging Face
   endpoint is *not* a workspace setting — it is an env var (`HF_ENDPOINT`,
   read by `huggingface_hub` inside `EmbeddingModelHub.download`); the wizard
   sets it server-side via `os.environ` alongside the API key, and the
   Settings page surfaces it for re-editing the same way. Chosen over adding
   new model fields: the hub already honours `HF_ENDPOINT` / `HF_HOME` /
   `GEOMEMORY_EMBEDDING_ROOT`, so no library change is needed.
3c. **Defaults are already in the library, the wizard just surfaces them.**
   LLM: provider `api`, base URL `https://api.kilo.ai/api/gateway/v1`
   (`default_kilo_base_url()` in `geomemory.qa.api_backend`), model id
   `kilo-auto/free` (`WorkspaceSettings.llm_model_id`). Text embedding:
   backend `onnx`, model `Xenova/all-MiniLM-L6-v2` (the quantized MiniLM
   export, `WorkspaceSettings.onnx_model_name`). Vision: OLMoEarth Nano v1.2
   (`image.olmoearth-nano-v12.v1`, the default vision space id). No new
   defaults to invent — the wizard is a UI over what the code already ships.
3d. **Shared model cache root = `GEOMEMORY_EMBEDDING_ROOT` env var.**
   `EmbeddingModelHub` already scans `GEOMEMORY_EMBEDDING_ROOT` *first* in its
   root list and downloads into it, so a model cached once is visible to every
   workspace — no per-workspace duplication. The wizard exposes this as a
   "shared model cache" field (default `~/.cache/huggingface`) that sets the
   env var server-side alongside the API key; a workspace may still set its
   own `embedding_path`, which is scanned *after* the shared root, so nothing
   is lost. Chosen over per-workspace caching: it matches the hub's existing
   precedence and requires no library change.
4. **vector_backend pattern fix.** Add `sqlite-vec` to the regex in
   `UpdateSettingsRequest`. Minimal, no model change.
5. **Doctor optional deps.** `geomemory.services.doctor.check_optional_deps`
   already imports modules in the running interpreter — the gateway runs in
   `geospatial`, so it already sees Pillow/fitz/docx. The bug is display-side:
   the Doctor page hid them behind a "no deps" branch. Fix is display-side
   plus confirming `optional_deps` flows through the doctor response (it
   already does).
6. **Qdrant: keep code, drop the docker service.** Removing Qdrant *code*
   would break `geomemory.index.qdrant_backend`, its unit/integration tests,
   `WorkspaceSettings.qdrant_url`/`qdrant_api_key`, the `index_service`
   dispatch, `doctor_qdrant`, and the Settings UI fields. Removing only the
   `qdrant` service + `qdrant_storage` volume from `docker-compose.yml`
   shrinks the image with zero code risk — the gateway already imports
   `qdrant_client` lazily and never requires it. sqlite-vec is the default;
   lancedb and qdrant remain opt-in.
7. **LLM is mocked in tests for now.** The user will verify real answers
   later. E2E exercises the abstention path, not live completion.

## Risks / Trade-offs

- **[Persisted workspace leaks path]** The state file records an absolute
  path that may not exist on another machine. Mitigation: on reopen, if the
  path is missing, fall back to closed (log a warning) instead of crashing.
- **[Wizard blocks all nav]** A user who opens the app while a workspace is
  mid-create could be stuck. Mitigation: Create/Open are the only exits; the
  gateway guarantees one is reachable.
- **[Online downloads in browser context]** ONNX model download happens in
  the gateway process (server-side), not the browser, so no CORS/network
  issues for the client.
- **[Playwright needs a live gateway]** E2E starts the gateway via
  docker-compose; if Docker is unavailable, the suite is skipped rather than
  silently passing.
- **[Qdrant docker removal]** If a user later sets `vector_backend=qdrant`
  with a `qdrant_url`, the gateway still works (lazy import); they just need
  to run Qdrant themselves. Documented in README.

## Migration Plan

1. Deploy server changes (state persistence, vector_backend fix).
2. Restart gateway; verify `GET /workspace` returns the previously open
   workspace.
3. Deploy web changes (wizard, switcher, settings, doctor, tests).
4. Rebuild the docker image without the qdrant service; verify `GET /health`
   is 200.
5. Run `pnpm test` (vitest) and `pnpm test:e2e` (playwright).

## Open Questions

- Should the active-workspace state file live inside the workspace dir or the
  gateway config dir? Deferring: workspace dir is simpler and is consistent
  with the single-writer invariant.
- Should downloads be allowed without an open workspace? Deferring: they are
  tied to a workspace's embedding path, so no.
- **WebGIS-engine deployability** — separate change, not this one.