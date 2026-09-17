## 1. Server fixes

- [x] 1.1 Fix `UpdateSettingsRequest.vector_backend` pattern to include `sqlite-vec`; verify with `conda run -n geospatial python -c "from geofront_api.schemas import UpdateSettingsRequest; UpdateSettingsRequest(vector_backend='sqlite-vec')"` → no ValidationError
- [x] 1.2 Default `CreateWorkspaceRequest.offline` to `false`; verify create response `settings.offline == false`
- [x] 1.3 Add workspace persistence: write active path to `.geofront/active_workspace` on create/open/close and reopen on gateway startup; verify `GET /workspace` returns open after a gateway restart
- [x] 1.4 Ensure `GET /doctor` exposes `environment.optional_deps` and that Pillow/PyMuPDF/python-docx flow through; verify with a curl against a running gateway
- [x] 1.5 Qdrant stays optional in doctor (no hard block, no removal from code); verify doctor returns 200 with `qdrant.client_installed` even when the server is unreachable
- [x] 1.6 Add server tests for the above (vector_backend, offline default, reopen, parent-path open); verify `conda run -n geospatial pytest server/tests -q` passes

## 2. Web: setup wizard + switcher + settings

- [x] 2.1 Add `SetupModal` component (Create/Open tabs; offline/online toggle; LLM provider + base URL + model id + key; embedding backend + model id + HF endpoint + shared cache root; vision default OLMoEarth Nano v1.2); verify it renders when `GET /workspace` is closed and blocks navigation
- [x] 2.1b Verify downloaded models are shared: download a model in one workspace, open a second workspace, assert it shows as already downloaded (no re-download)
- [x] 2.2 Wire `SetupModal` into `AppShell` as the route overlay; verify the URL cannot advance past it without an open workspace
- [x] 2.3 Update `WorkspaceSwitcher` to accept typed paths and folder-pick of a parent dir; verify open-by-parent via the wizard
- [x] 2.4 Remove the "Model Paths" (GGUF) section from `SettingsPage`; verify the DOM has no GGUF-path labels
- [x] 2.5 Fix offline-hint visibility: show only when `offline == true`; verify download buttons enabled when online
- [x] 2.6 Add i18n keys (en + fa) for the wizard and doctor changes; verify `pnpm build` passes (i18n keys exist)

## 3. Web: doctor page

- [x] 3.1 Surface `environment.optional_deps` in Doctor (Pillow, PyMuPDF, opendataloader-pdf, python-docx, rasterio, shapely, geopandas); verify the DOM shows them as installed
- [x] 3.2 Remove the "Downloads require offline=false" hint from Settings/Doctor when online; verify it only appears when `offline == true`
- [x] 3.3 Ensure no `[object Object]` text and no GGUF-path labels anywhere in Doctor; verify with a Playwright assertion

## 4. Web: test harness

- [x] 4.1 Ensure `pnpm install` is clean and `pnpm build` succeeds
- [x] 4.2 Add Vitest tests covering: setup wizard open/close, settings save (no 422), doctor dep list, offline-hint visibility; verify `pnpm test` passes
- [x] 4.3 Add Playwright E2E with screenshots: wizard → create → overview → settings save → doctor → ingest → search → ask, plus RTL flip and empty/error states; verify `pnpm test:e2e` passes and screenshots are written
- [x] 4.4 Wire docker-compose so the E2E suite runs against a live gateway; verify the suite runs green from a clean checkout

## 5. Docker

- [x] 5.1 Remove the `qdrant` service from `docker-compose.yml` (image + volume + healthcheck) to shrink the image — code/tests/settings stay intact; verify `docker compose config` is valid and the gateway still boots without Qdrant
- [x] 5.2 Verify the gateway image builds and `GET /health` returns 200 with no Qdrant dependency

## 6. Final gate

- [x] 6.1 `conda run -n geospatial ruff check server/src libs/geoagent/src libs/geomemory/src` → exit 0
- [x] 6.2 `conda run -n geospatial pytest server/tests -q` → green
- [x] 6.3 `pnpm lint && pnpm build && pnpm test` → clean
- [x] 6.4 `pnpm test:e2e` → green with screenshots
- [x] 6.5 Update `tasks/todo.md` and archive this change

## Out of scope (deferred)

- **Deployable-as-WebGIS-engine.** Making the gateway a reusable embeddable engine (auth, multi-tenant, OpenAPI as a product, CDN-friendly asset serving) is a separate, heavier change. Omitted for now — it gets its own OpenSpec change when you want it.