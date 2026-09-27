## Why

Recent manual testing exposed critical integration and runtime blockers across the web frontend and FastAPI gateway:
1. Workspace creation failed due to legacy hardcoded filesystem paths (`/mnt/data/...`) instead of dynamic project-relative or configurable roots.
2. Ingest failed with HTTP 422 Unprocessable Entity because the HTTP client forced `Content-Type: application/json` on `FormData` multipart payloads.
3. Model scanning and downloads referenced outdated dev machine paths rather than canonical user caches (`~/.cache/huggingface`) and environment overrides.

Manual "click-and-fail" testing button by button is slow and error-prone. A comprehensive, automated audit across all 18 web routes, API contracts, forms, and background job loops is needed to find and resolve all remaining contract mismatches, runtime exceptions, and UI interaction bugs systematically.

## What Changes

- **Automated Frontend & Gateway Contract Audit**: Systematically map every frontend API call in `apps/web/src/api/` against every router in `server/src/geofront_api/routers/` to verify request method, body format (`application/json` vs `multipart/form-data`), query parameters, path variables, and response envelope handling.
- **Dynamic Path & Environment Handling**: Ensure all runtime workspace data, model caches, and state markers default to `<project_root>/Workspaces`, `~/.cache/huggingface`, or explicit environment variables (`GEOFOND_WORKSPACE`, `GEOMEMORY_EMBEDDING_ROOT`) without hardcoded absolute machine paths.
- **Baseline Code Health (Lint, Typecheck, Test)**: Before visual browser debugging, bring `pnpm lint`, `pnpm build` (`tsc`), and `pnpm test` to 100% green to eliminate underlying syntax, type, and import flaws.
- **Autonomous Visual & Runtime Defect Loop (Playwright + Vision Model)**: Turn frontend verification into an observable, automated loop:
  1. Crawl all 18 web routes using Playwright / Chrome DevTools automation.
  2. Aggregate console errors, network failures, and React runtime crashes.
  3. Capture full-page screenshots for every route and state.
  4. Inspect and analyze screenshots with a Vision Model to identify visual defects (broken layouts, clipping, RTL misalignments, empty cards).
  5. Apply the single-issue discipline: pick one reproducible bug at a time, fix it, verify with re-tests and browser automation, commit, and proceed to the next issue.
- **Automated E2E Test Suite**: Add comprehensive Playwright / Vitest integration tests that walk all major UI flows (workspace open/create, collection create/delete, document ingest, search with filters, agent chat, doctor diagnostics) to prevent future regression.

## Capabilities

### Modified Capabilities
- `web-app`: Enforce strict multipart form request handling, ensure all button actions and forms surface feedback without uncaught rejections or 422/500 errors, and verify UI flows across all pages.
- `gateway-server`: Enforce dynamic project-root-relative workspace resolution, resilient model hub scanning without hardcoded machine paths, and consistent schema validation across all ingestion and agent endpoints.

## Impact

- `server/src/geofront_api`: State resolution, ingest validation, model hub scanning, and router error handling.
- `apps/web/src/api`: HTTP request abstraction, form data handling, endpoint signature alignment.
- `apps/web/src/features/*`: IngestPage, SettingsPage, CollectionsPage, AgentChatPage, SearchPage, and other interactive components.
- Automated tests: `apps/web/e2e/` and `server/tests/` suites expanded with complete coverage for verified flows.
