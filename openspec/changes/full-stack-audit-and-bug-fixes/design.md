## Context

The GeoFoundation architecture pairs a Python FastAPI gateway (`server/src/geofront_api`) with a React Vite SPA (`apps/web`). The gateway acts as a strict facade over the `geomemory` and `geoagent` libraries, exposing OpenAPI endpoints consumed by `apps/web`.

Prior ad-hoc development introduced hardcoded filesystem assumptions (`/mnt/data/...`), improper `Content-Type` header handling on multipart uploads, and unverified edge cases in UI state machines. This design specifies an automated, reproducible audit and fix approach across both tiers.

## Goals / Non-Goals

**Goals:**
- Eliminate all hardcoded developer machine paths across `server/` and `libs/`, defaulting to `<project_root>/Workspaces` and `~/.cache/huggingface`.
- Standardize web HTTP client serialization in `apps/web/src/api/client.ts` to support both `FormData` (omitting `Content-Type` for boundary generation) and JSON.
- Verify every interactive control across all 18 SPA pages (Overview, Settings, Doctor, Collections, Entities, Ingest, Assets, Search, Ask, Index, Feedback, Eval, Agent, Conversations, Tools, Playbooks, Farms, Maps) against the gateway endpoints.
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

### Decision 3: Two-Tier Audit Methodology
- **Tier 1 (Static Contract Audit)**:
  1. Validate OpenAPI schema generation against actual router endpoints.
  2. Run `pnpm gen:api` and `tsc -b` to guarantee full TypeScript type safety on all requests/responses.
  3. Validate all router inputs against schema models.
- **Tier 2 (Dynamic Playwright & Pytest Audit)**:
  1. Run the full Python test suite (`pytest server/tests -q`).
  2. Run the frontend unit & component test suite (`pnpm test`).
  3. Run comprehensive browser-level integration tests (`pnpm test:e2e` or automated headless Playwright scripts) walking every major user journey.

## Risks / Trade-offs

- [Risk] Running full browser tests might require live model downloads. → Mitigation: Exercise offline mode and mock LLM/embedding fixtures in CI/testing; allow online mode for manual validation.
- [Risk] Active workspace state files might leak between test runs. → Mitigation: Autouse pytest fixture isolating `GEOFONT_STATE_PATH` to temporary directories.
