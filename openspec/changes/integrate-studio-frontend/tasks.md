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
- [ ] Verify gateway health probe on startup (`GET /api/v1/health`).
- [ ] Connect live scene search to `/api/v1/data/search`.
- [ ] Connect scene download job to `/api/v1/data/download` with SSE progress streaming (`/api/v1/jobs/{id}/events`).
- [ ] Connect grounded QA to `/api/v1/knowledge/ask`.
- [ ] Connect training lab partial_fit to `/api/v1/models/train`.
- [ ] Verify bilingual Persian (فارسی) text and RTL mirroring while maintaining LTR cartographic map.
