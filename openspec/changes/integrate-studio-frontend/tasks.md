# Tasks: integrate-studio-frontend

## Setup & Scaffolding
- [x] Create branch `feat/studio-react` preserving `apps/web`.
- [x] Migrate production Studio frontend files from desktop into `apps/studio/`.
- [x] Configure `@geomind/studio` package identity and scripts (`pnpm check`, `pnpm build`, `pnpm dev`).
- [x] Configure Vite dev server proxy to gateway at `http://localhost:8000/api`.
- [x] Install dependencies with pnpm using local mirror and approve `esbuild` binary.
- [x] Verify zero TypeScript errors via `pnpm check`.
- [x] Verify production single-file build succeeds via `pnpm build`.

## Gateway Connectivity & Testing
- [x] Verify gateway health probe on startup (`GET /api/v1/health`).
- [x] Connect live scene search to `/api/v1/data/search`.
- [x] Connect scene download job to `/api/v1/data/download` with SSE progress streaming (`/api/v1/jobs/{id}/events`).
- [x] Connect grounded QA to `/api/v1/knowledge/ask`.
- [x] Connect training lab partial_fit to `/api/v1/models/train`.
- [x] Verify bilingual Persian (فارسی) text and RTL mirroring while maintaining LTR cartographic map.
