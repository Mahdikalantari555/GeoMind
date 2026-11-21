# Proposal: add-svelte-studio-app

> **SUPERSEDED — DO NOT SYNC SPECS.** 2026-11-14: `feat/svelte-studio` was
> deleted and `feat/studio-react` merged — the React 19 Studio
> (`apps/studio`) is the product front. The tasks below were completed
> against the Svelte app, which was then replaced wholesale. Archived as a
> historical record only; the `specs/` deltas here describe the removed
> Svelte app and MUST NOT be synced into main specs.

## Why

The existing React web app (`apps/web`) proved effectively unusable in
practice: the LLM often did not respond, no maps were available, and every
surface had problems. The product vision
(`research/startup-vision/VISION.md`) calls for a map-first studio built in
Svelte with shadcn-svelte, where a researcher draws an ROI on a map, downloads
satellite data for it with live progress, and gets cited answers. This change
delivers the studio shell and the money demo: **draw ROI → download data →
layers appear, with progress the user can trust.**

`apps/web` is frozen by this change: no new features; it stays installable as
reference and is deleted when Studio reaches parity.

## What Changes

- Add `apps/studio/` — a SvelteKit (Svelte 5) SPA, package `@geomind/studio`,
  talking ONLY to the gateway `/api/v1` (AGENTS.md invariant 1). Static
  adapter, no SSR.
- shadcn-svelte + Tailwind with the **scientific-instrument** theme
  (dark-first, monospace numerics for coordinates and stats).
- Map-first home: MapLibre GL map, layer tree (base, scenes, products,
  doc overlays, ROIs), ROI drawing (polygon/bbox), ROIs saved as first-class
  objects via the gateway.
- Acquire page: scene search for the current ROI (sensor + date range),
  download jobs, live progress, queue view, cancel.
- Server: `job.progress` — long jobs expose progress (stage, percent, detail)
  over the existing SSE event stream and `GET /jobs/{id}`. One mechanism
  feeds every progress bar in the app.
- **No dead ends** (the lesson from `apps/web`): every page has designed
  empty/error/loading states; LLM-unavailable is a designed state (retrieval
  continues, config offered after first answer); map renders with an offline
  basemap; a health/doctor surface diagnoses workspace, index, LLM, and data
  source status.
- Onboarding: first launch → "Try sample workspace" seeds a bundled,
  pre-indexed demo → first cited answer in under 2 minutes.
- Freeze `apps/web`: remove from dev docs as the primary app; keep in repo.

## Capabilities

### New Capabilities
- `studio-shell` — app frame, routing, theming, no-dead-ends contract,
  health surface.
- `studio-map-roi` — map home, layer tree, ROI draw/save/render.
- `studio-acquire` — scene search, download jobs, progress, queue.
- `studio-onboarding` — first-run sample workspace flow.
- `gateway-job-progress` — server-side progress reporting for long jobs
  (SSE + REST).

### Modified Capabilities
- `web-app` — marked frozen; parity with Studio ends its lifecycle
  (deletion deferred to a later change).

## Impact

- **Apps:** new `apps/studio/` (pnpm, SvelteKit, shadcn-svelte).
- **Server:** job progress events; no route changes beyond job progress
  fields. OpenAPI regenerated (`pnpm gen:api` equivalent for studio).
- **Libs:** none. Download orchestration lives at the gateway; scene
  acquisition itself is the `data_engine` `add-scene-fetcher` change.
- **Docs:** `docs/SPEC_WEB.md` gains a Studio section; AGENTS.md app table
  gains `apps/studio`.

## Dependencies

- Implemented before or alongside `add-scene-fetcher` (data_engine lib).
  The Acquire page ships with a designed empty state when no fetcher is
  available — the no-dead-ends rule applies to rollout order too.
