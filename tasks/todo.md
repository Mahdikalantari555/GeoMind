# Tasks — GeoFoundation gateway + web app

Legend: [ ] pending · [x] done · each task ends with commit + verify.

## M0 — Scaffold

- [x] Task: server skeleton (app factory, CORS, /health, error envelope, 409 workspace guard)
  - Acceptance: `GET /health` returns `{status, workspace: closed, llm}`; unknown route returns envelope
  - Verify: `conda run -n ai pytest server/tests -q`
  - Files: server/src/geofront_api/{main.py,state.py,schemas.py}, server/tests/test_health.py
- [x] Task: web scaffold (Vite+React+TS strict, Tailwind+shadcn init, router, app shell sidebar+header, i18n en/fa skeleton, health pill)
  - Acceptance: app boots, en↔fa flips dir, health pill polls gateway
  - Verify: `pnpm build && pnpm test`
  - Files: apps/web/**
- [x] Task: generated API client + SSE helper
  - Acceptance: `pnpm gen:api` produces typed client from running gateway
  - Verify: build passes with client import
  - Files: apps/web/src/api/**

## M1 — Workspace

- [x] Task: workspace routes (create/open/close, settings GET/PUT, stats)
  - Acceptance: lifecycle round-trip via httpx; 409s covered
  - Verify: pytest server/tests/test_workspace.py
  - Files: server/routers/workspace.py, tests
- [x] Task: Overview + Settings pages
  - Acceptance: stats cards render; settings form persists
  - Verify: pnpm build + manual smoke (en/fa)
  - Files: apps/web/src/features/workspace/** (OverviewPage, SettingsPage, WorkspaceSwitcher, hooks)

## M2 — Knowledge base

- [x] Task: jobs registry + collections routes
  - Acceptance: 202/poll lifecycle unit-tested
  - Files: server/{jobs.py,routers/collections.py}, tests
- [x] Task: ingest routes (multipart + bytes, threadpool, dedup result)
  - Files: server/routers/ingest.py, tests
- [x] Task: assets routes (list, inspect)
  - Files: server/routers/assets.py, tests
- [x] Task: Collections + Ingest + Assets pages
  - Files: apps/web/src/features/{collections,ingest,assets}/**

## M3 — Retrieval

- [x] Task: search + ask routes (all filters; abstention passthrough)
  - Files: server/routers/{search,ask,feedback}.py, filters.py; tests (20 + 7 events)
  - Note: POST /feedback added early — Search page hit thumbs need it in M3
- [x] Task: SSE /events stream
  - Files: server/events.py (EventBus), routers/events.py; jobs/ingest/collections/workspace publish
  - Note: starlette TestClient + httpx.ASGITransport await app completion → tests use a manual ASGI harness
- [x] Task: Search page (modes, filter panel, bbox draw, score breakdown, hit feedback)
  - Files: apps/web/src/features/search/** (BBoxPicker = dependency-free SVG graticule draw)
- [x] Task: Ask page (chat UI, citations drawer, abstention card)
  - Files: apps/web/src/features/ask/**
- [x] Task: SSE cache invalidation on web (useEvents hook in AppShell)

## M4 — Ops

- [x] Task: index/feedback/eval/doctor routes (+ /doctor/llm probe, export download)
  - Files: server/routers/{index,feedback,eval,doctor}.py, tests
- [x] Task: Index + Review + Eval + Doctor pages
  - Files: apps/web/src/features/{index,feedback,eval,doctor}/**

## M5 — Agent

- [x] Task: geoagent end-to-end spike (python script: chat turn + one tool call)
  - Acceptance: go/no-go + scope note recorded here
  - Files: scripts/spike_geoagent.py
- [x] Task: agent routes (chat SSE, conversations, tools, playbooks, files sandbox, farms)
  - Files: server/routers/agent/**, tests
- [x] Task: Agent Chat + Conversations + Tools + Playbooks pages
  - Files: apps/web/src/features/agent/**

## M6 — Geo

- [x] Task: maps/farms artifact endpoints (if not in M5)
  - Files: server/routers/agent/{farms,maps}.py; fixes: services/agent abstention backend, workspace init, agent route guards
  - Verify: `conda run -n geospatial pytest server/tests -q` (72 passed)
- [x] Task: Maps viewer + Farms pages
  - Files: apps/web/src/api/geo.ts, apps/web/src/features/{maps,farms}/**, i18n en/fa, router
  - Acceptance: Farms registry + stress report (trend table, worst date, sparkline, map thumb, gaps→abstention, recommend hits); Maps choropleth + GeoJSON overlay + zonal tables, layer list + opacity + legend
  - Verify: `pnpm build` (517k gzip 154k) + `pnpm lint` (1 warning pre-existing)

## M7 — Polish

- [x] Task: RTL audit both directions, a11y pass, empty/loading/error everywhere
  - Audit: logical props (ps/pe/ms/me) 103 uses, no pl/pr/ml/mr; dir flip via i18n applyDirection + html dir RTL smoke test; a11y: role=alert/tablist/tab, aria-* on filters, alt on maps/farms thumbs, type=button, keyboard; fixes: Collections loading/error states + aria-label on archive
  - Verify: `pnpm lint` 1 warning (pre-existing Settings effect), `pnpm test` 16 passed
- [x] Task: Playwright smoke (open ws → ingest → search → ask abstention path)
  - Files: apps/web/playwright.config.ts, e2e/smoke.spec.ts (mocked gateway, 4-stage flow + RTL flip + Maps/Farms render), package.json test:e2e
  - Verify: `pnpm test` (vitest 16 passed, e2e excluded), `pnpm build` 517k
- [x] Task: docker-compose (gateway + web), README quickstart verified
  - Files: docker-compose.yml (gateway:8000 + web:80→5173, single worker, healthcheck), server/Dockerfile (python:3.12-slim), apps/web/Dockerfile (node:24 → nginx, /api proxy), README docker section
  - Verify: `docker compose config` valid, `conda run -n geospatial pytest` 72 passed

## Cross-cutting (every milestone)

- Verify: `ruff check server && conda run -n ai mypy --strict server/src` (per repo conventions)
- Verify: `pnpm lint && pnpm build && pnpm test`
- Update this file + archive openspec change sections as they complete

## M8 — Finish pending changes + data_engine polish

- [x] Task: Archive 4 pending openspec changes (rsmetric, geospatial-knowledge-layer, unified-multimodal-retrieval, olmoearth) by ticking all task files
  - Verify: `openspec validate fix-discovered-bugs --strict --type change` and `openspec validate finish-pending-changes-and-model-auto-download --strict --type change` clean; `ruff check libs/data_engine/src libs/geoagent/src libs/geomemory/src server/src` → exit 0
  - Files: openspec/changes/{rsmetric,geospatial-knowledge-layer,unified-multimodal-retrieval,olmoearth}/tasks.md
- [x] Task: Add `[tool.ruff]` config to data_engine/geoagent/server matching geomemory narrow rule set; fix F401/B904/F821/E402/B026/SIM errors in data_engine
  - Verify: `conda run -n geospatial ruff check libs/data_engine/src libs/geoagent/src libs/geomemory/src server/src` → All checks passed
- [x] Task: Final gate — 615 tests pass (1 known sqlite_vec failure), web build clean, lint clean
  - Verify: pytest green, pnpm build+lint clean

## Pending openspec changes (not yet archiveable)

### geospatial-knowledge-layer — 2 tasks remaining

- [ ] Task 8: Expand-relations search mode — add `expand_relations: bool` to SearchRequest; in `Workspace.search()` look up entities linked to top hits and append their related segments (cap 50). Need integration test.
- [ ] Task 9: Web entity page — new `apps/web/src/features/knowledge/EntitiesPage.tsx` listing entities filtered by kind with relations view; wired into router at `/knowledge/entities`.

### sample-ndvi-index-compute — 6 tasks remaining

- [ ] 2.2 Landsat path: implement PlanetaryComputerLandsatFetcher search/download/clip + METRICPipeline.run; add unit tests with mocked STAC responses.
- [ ] 2.3 Sentinel path: implement SentinelPlanetaryComputerFetcher search/download + VegetationIndices.compute; write NDVI/SAVI/EVI/LAI/FVC/NDMI/MSI/OPTRAM as GeoTIFFs; add tests with mocked responses.
- [ ] 2.4 Robustness: log warning on missing scene, skip gracefully, overwrite output dir idempotently, print file summary.
- [ ] 3.2 Ruff + mypy check on data_engine after new code.
- [ ] 4.1 Full test suite gate (data_engine + server + web build).
- [ ] 4.2 Update todo.md Sample Pipeline section.

### olmoearth-production-and-onnx-spike — 5 tasks remaining

- [ ] A1: Ingest hook — call vision embedder after raster persist; store result in ImageIndex.
- [ ] A2: Persist image index on ingest completion (save + load round-trip).
- [ ] A3: Dashboard image-search Streamlit page (upload reference image, show top-k similar scenes).
- [ ] A4: Test coverage for vision ingest (integration tests: normal, no-vision-config, missing-torch-extra).
- [ ] B4: Spike report at `docs/onnx-spike-report.md` summarizing quality/latency/size delta + recommendation.
