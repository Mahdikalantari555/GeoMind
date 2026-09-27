## 1. Dynamic Paths and Ingest Serialization

- [x] 1.1 Verify dynamic workspace root resolution in `server/src/geofront_api/state.py` and test isolation in `server/tests/conftest.py` with `conda run -n geospatial pytest server/tests/test_workspace.py`
- [x] 1.2 Verify `EmbeddingModelHub` scan root removal of hardcoded `/mnt/data` in `libs/geomemory/src/geomemory/embeddings/hub.py` with `conda run -n geospatial pytest libs/geomemory/tests/unit/test_embedding_auto_download.py`
- [x] 1.3 Fix multipart header generation in `apps/web/src/api/client.ts` to omit `Content-Type` for `FormData` and verify with `cd apps/web && pnpm lint && pnpm test`

## 2. Baseline Static Health & Contract Alignment

- [x] 2.1 Run static analysis consolidation in `apps/web`: execute `pnpm lint`, `pnpm build` (`tsc -b`), and `pnpm test`; fix all type errors and lint violations before touching browser testing
- [x] 2.2 Audit all client endpoints in `apps/web/src/api/` against `server/src/geofront_api/routers/` (checking parameter names, schemas, query parameters, and HTTP methods) and fix any mismatches
- [x] 2.3 Run OpenAPI client generator `pnpm gen:api` in `apps/web` and compile types with `pnpm build` to verify zero type errors

## 3. Automated Crawler, Telemetry & Screenshot Capture

- [x] 3.1 Implement automated route crawler script using Playwright / Chrome DevTools navigating all 18 web routes in both LTR and RTL (`fa`) modes
- [x] 3.2 Aggregate telemetry report during crawl: collect all console errors (`console.error`), network failures (HTTP >= 400), and React runtime error boundaries
- [x] 3.3 Capture full-page screenshots for every route and interactive overlay into an audit artifact directory (`apps/web/test-results/audit/`)

## 4. Vision-Driven Defect Analysis & Iterative Fix Loop

- [x] 4.1 Analyze captured route screenshots using Vision Model inspection to detect visual anomalies (clipping, overlapping text, broken layouts, RTL alignment flaws, unstyled fallback UI)
- [x] 4.2 Execute single-issue iteration discipline: select the highest-confidence defect from telemetry or vision report, reproduce locally, apply targeted fix, re-verify with tests and browser automation, commit individually, and repeat until clean:
  - [x] 4.2.1 Ingest & Assets flows (`IngestPage.tsx`, `AssetsPage.tsx`): multi-file input selection (`multiple` attribute enabled for all file pickers/dropzones), batch upload queue, collection selector, indexing toggle, table actions, asset delete/preview, job polling
  - [x] 4.2.2 Workspace & Settings flows (`OverviewPage.tsx`, `SettingsPage.tsx`, `DoctorPage.tsx`): workspace create/open/close modal & buttons, LLM key updates, scan models trigger, doctor rerun diagnostics
  - [x] 4.2.3 Search & Ask flows (`SearchPage.tsx`, `AskPage.tsx`): query submit buttons, modality switches, spatial bbox filter interactive controls, pagination, citation cards, abstention states
  - [x] 4.2.4 Agent & Knowledge flows (`AgentChatPage.tsx`, `ToolsPage.tsx`, `PlaybooksPage.tsx`, `CollectionsPage.tsx`, `EntitiesPage.tsx`, `FarmsPage.tsx`, `MapsPage.tsx`): chat send/stop buttons, tool invoke triggers, playbook run buttons, collection CRUD modals, farm card actions, map layers toggle
  - [x] 4.2.5 Global controls & layout: sidebar collapse/expand, language toggle (`en`/`fa`), dark/light theme switch, breadcrumbs, notification toasts, modal dismiss triggers

## 5. End-to-End Verification & Final Sign-Off

- [x] 5.1 Run full Python backend test suite (`conda run -n geospatial pytest server/tests -q`) and verify 100% pass rate
- [x] 5.2 Run full web test suite (`pnpm test` and `pnpm build` in `apps/web`) and verify zero failures
- [x] 5.3 Execute end-to-end integration test with Playwright covering workspace creation, file ingestion, search, and agent chat
- [x] 5.4 Run final crawl to confirm zero console errors, zero network failures, and verified visual screenshots
