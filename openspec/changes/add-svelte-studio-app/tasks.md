# Tasks: add-svelte-studio-app

Order: shell first (map works early), server progress in parallel with
Acquire UI. Acquire page ships with its fetcher-absent empty state so the app
is complete even before `add-scene-fetcher` lands.

## 1. Scaffold

- [x] 1.1 Create `apps/studio/` — SvelteKit (Svelte 5, runes), adapter-static
      SPA mode, TypeScript strict, pnpm; package `@geomind/studio`
- [x] 1.2 Set up shadcn-svelte + Tailwind with the instrument theme tokens
      (dark-first palette, monospace numeric style); base layout with top bar,
      layer panel, agent rail placeholder
- [x] 1.3 Wire gateway API client (typed from OpenAPI schema; shared base URL
      config, /api/v1 only)
- [x] 1.4 Quality gates runnable: `pnpm check` (svelte-check strict), `pnpm
      lint`, `pnpm test` (Vitest); all green on the bare shell
- [x] 1.5 Mark `apps/web` frozen in root AGENTS.md + docs/SPEC_WEB.md (frozen
      note, primary app = apps/studio)

## 2. Studio shell (studio-shell)

- [x] 2.1 No-dead-ends states: global gateway-unreachable/reconnect state;
      per-page empty/error/loading patterns; no raw error dumps
- [x] 2.2 Health/doctor view: workspace, index, LLM probe, data-source, and
      storage checks each with pass/fail + fix action
- [x] 2.3 Command palette (Ctrl/Cmd+K) with workspace-switcher in top bar
- [x] 2.4 Unit tests: state store, health checks, no-dead-ends renderers

## 3. Map + ROI (studio-map-roi)

- [x] 3.1 MapLibre GL map canvas as home route with bundled offline-capable
      basemap style (renders with zero keys, offline fallback)
- [x] 3.2 Layer tree (Base/Scenes/Products/Doc overlays/ROIs) with visibility
      toggles + persisted collapse state
- [x] 3.3 ROI draw tools (polygon, bbox) → name/save via gateway → render
      with geodesic area
- [x] 3.4 ROI list/select/delete; current-ROI store consumed by Acquire
- [x] 3.5 SSE-driven scene-layer appearance (no polling)
- [x] 3.6 Unit tests: ROI store, layer tree state, area calculation

## 4. Gateway job progress (gateway-job-progress)

- [ ] 4.1 Job model: stage/percent/detail fields; progress reporting helper
      (bounded rate ~4/s) for job writers
- [ ] 4.2 Emit `job.progress` over existing SSE; include progress in `GET
      /jobs/{id}`; reconnect-catch-up semantics honored
- [ ] 4.3 Adopt reporting in existing long ops (ingest/index at minimum)
- [ ] 4.4 Server tests: progress fields, SSE events, rate cap, catch-up
- [ ] 4.5 Regenerate OpenAPI schema; server ruff + mypy --strict + tests pass

## 5. Acquire page (studio-acquire)

- [ ] 5.1 Scene search UI for current ROI (sensor + date range) against
      gateway search endpoint; "already owned" markers
- [ ] 5.2 Download job start → queue view (queued/running/done/failed/cancelled)
- [ ] 5.3 Live progress rendering from SSE with REST catch-up on reconnect
- [ ] 5.4 Cancel + retry actions; per-scene resumability display
- [ ] 5.5 Auto-ingest chain (download → ingest → index) shown as one progress
      story; scene appears in Resources + as map layer when done
- [ ] 5.6 Fetcher-absent designed empty state with install guidance
- [ ] 5.7 Unit tests: search filters, queue state machine, progress recovery

## 6. Onboarding (studio-onboarding)

- [ ] 6.1 Bundle sample seed assets (sample scene reference, farms GeoJSON,
      sample PDFs) + seed routine creating a pre-indexed demo workspace
- [ ] 6.2 First-launch empty state with primary "Try sample workspace" +
      secondary real-workspace path
- [ ] 6.3 Guided first question → cited answer; retrieval-only mode without
      LLM; LLM config affordance deferred until after first answer
- [ ] 6.4 Unit tests: first-run routing, seed routine, deferred-config states

## 7. Validation

- [ ] 7.1 All studio gates green: check/lint/test; mypy --strict + ruff +
      tests green for server changes
- [ ] 7.2 Manual 2-minute walkthrough recorded: launch → sample workspace →
      question → cited answer
- [ ] 7.3 (Deferred) e2e Playwright suite — tracked for a later change
