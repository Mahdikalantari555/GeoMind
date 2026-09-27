## Context

The GeoFoundation architecture pairs a Python FastAPI gateway (`server/src/geofront_api`) with a React Vite SPA (`apps/web`). The gateway acts as a strict facade over the `geomemory` and `geoagent` libraries, exposing OpenAPI endpoints consumed by `apps/web`.

Prior ad-hoc development introduced hardcoded filesystem assumptions (`/mnt/data/...`), improper `Content-Type` header handling on multipart uploads, and unverified edge cases in UI state machines. This design specifies an automated, reproducible audit and fix approach across both tiers.

## Goals / Non-Goals

**Goals:**
- Eliminate all hardcoded developer machine paths across `server/` and `libs/`, defaulting to `<project_root>/Workspaces` and `~/.cache/huggingface`.
- Standardize web HTTP client serialization in `apps/web/src/api/client.ts` to support both `FormData` (omitting `Content-Type` for boundary generation) and JSON.
- Support multiple file selection in Ingest and Asset file inputs/dropzones (`multiple` attribute enabled, batch queue/upload handling).
- Verify every interactive control, button, form, tab, and function across all 18 SPA pages (Overview, Settings, Doctor, Collections, Entities, Ingest, Assets, Search, Ask, Index, Feedback, Eval, Agent, Conversations, Tools, Playbooks, Farms, Maps) to guarantee expected performance: immediate visual feedback, disabled states during submission, no dead clicks, and proper error/success surfacing.
- Establish automated E2E test coverage verifying the complete workspace → collection → ingest → search → ask lifecycle.

**Non-Goals:**
- Redesigning UI styling, themes, or layout components.
- Changing core mathematical pipelines in `libs/data_engine` or model training in `libs/geolearn`.
- Adding multi-tenant or remote database backends (preserves single-writer SQLite invariant).

## Decisions

### Decision 1: Intelligent Header Management in Web Client
- **Choice**: Use the standard `Headers` API in `apps/web/src/api/client.ts`. If `init.body instanceof FormData`, do not set `Content-Type`. If `init.body` is present and not `FormData`, set `Content-Type: application/json` only if not explicitly set.
- **Rationale**: Browsers must compute the multipart boundary string dynamically. Setting `Content-Type: application/json` breaks multipart body parsing in Starlette / FastAPI, causing 422 Unprocessable Entity.
- **Alternative considered**: Requiring every caller in `api/*.ts` to specify headers explicitly. Rejected because developers will inevitably forget, causing subtle regressions.

### Decision 2: Dynamic Project-Root Resolution for Workspaces and Caches
- **Choice**: Resolve default workspace root as `Path(__file__).resolve().parents[3] / "Workspaces"`, overridable by `GEOFOND_WORKSPACE` and container `/workspace`. Models default to `~/.cache/huggingface` or `GEOMEMORY_EMBEDDING_ROOT`.
- **Rationale**: Keeps dev workspaces inside the gitignored project directory without depending on any external volume or hardcoded absolute path.
- **Alternative considered**: Storing workspaces in OS temp directory. Rejected because user workspaces must persist across gateway reboots.

### Decision 3: Multi-Stage Observable Frontend Loop & Vision-Driven Inspection
- **Choice**: Structure frontend verification into a closed, observable diagnostic loop rather than ad-hoc bug hunting:
  1. **Stage 0 (Static Baseline)**: First bring `pnpm lint`, `pnpm build` (`tsc -b`), and `pnpm test` to 100% green. 80% of UI runtime errors trace back to TypeScript/ESLint violations and unhandled edge cases; eliminating them establishes a stable baseline before opening a browser.
  2. **Stage 1 (Automated Crawl)**: Use Playwright / Chrome DevTools to systematically crawl all 18 web routes in both LTR and RTL (`fa`) modes.
  3. **Stage 2 (Telemetry & Screenshot Capture)**:
     - Listen to and collect all `page.on('console', msg => ...)` error messages.
     - Intercept and log all failed network requests (`response.status() >= 400`).
     - Detect uncaught React error boundaries and runtime exceptions.
     - Capture full-page screenshots (`page.screenshot({ fullPage: true })`) for every route and active modal/panel state into an audit directory (`/tmp/audit-screenshots/` or `apps/web/test-results/audit/`).
  4. **Stage 3 (Vision Model Analysis)**: Use vision-capable inspection to analyze the captured screenshots:
     - Detect visual anomalies: overlapping text, clipped buttons, misaligned RTL elements (`ps`/`pe` vs `pl`/`pr`), broken layouts, blank component cards, or unstyled error boundaries.
  5. **Stage 4 (Single-Bug Iteration Discipline)**:
     - Follow the strict loop: `Discover -> Reproduce -> Fix -> Verify (tests + browser automation) -> Commit -> Repeat`.
     - Never mix multiple bug categories in one commit.
     - Continue until zero reproducible console errors, network failures, or visual defects remain.
- **Rationale**: Directing an agent to "find and fix all UI bugs" causes context overflow, random scattered edits, and regressions. Turning verification into a reproducible crawl-telemetry-screenshot-vision loop provides concrete observability and step-by-step convergence.
- **Alternative considered**: Relying solely on manual clicking or DOM snapshot assertions without visual screenshot analysis. Rejected because DOM snapshots miss visual clipping, styling regressions, z-index overlaps, and RTL layout defects.

## Risks / Trade-offs

- [Risk] Running full browser tests might require live model downloads. → Mitigation: Exercise offline mode and mock LLM/embedding fixtures in CI/testing; allow online mode for manual validation.
- [Risk] Active workspace state files might leak between test runs. → Mitigation: Autouse pytest fixture isolating `GEOFONT_STATE_PATH` to temporary directories.
