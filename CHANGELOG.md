# Changelog

All notable changes to GeoMind are recorded here. Change proposals live in
`openspec/changes/` (active) and `openspec/changes/archive/` (delivered).

## 2026-11-24 — ship-and-measure-agent

Final delivery tranche of the product-readiness audit.

- **Docker ships Studio.** `docker compose up` now serves the map-first Studio
  build on `:5174` through an nginx `/api` proxy; the frozen admin console is
  opt-in via `--profile reference`. Single-uviworker gateway invariant intact.
- **Published agent baseline.** `docs/benchmarks/report.md` with a frozen
  protocol, retrieval ablation, abstention confusion matrix and a
  machine-enforced 100% citation-resolution invariant. CI reruns the protocol.
- **Live agent chat.** Studio's AgentRail now uses only the real `/agent/chat`
  SSE flow: conversation handoff, ToolRun-audit tool cards, `[S#]`→`[n]`
  citation normalization and an explicit degraded state. Scripted replies are
  retired.
- **Vision-search spike.** Headless tiles-to-embedding bridge proven offline;
  Studio view deferred with prerequisites recorded in ADR 0003.
- **Agent exposure surface.** Five learning-loop tools and a token-bounded tool
  manifest with `list_tools(family)` expansion; MCP transport deferred per
  ADR 0004.

## 2026-11-24 — sentinel1-and-scene-fetch

- Sentinel-1 GRD/RTC fetchers (vv/vh, orbit-tagged resumable directories,
  `cloud_available=False` for SAR) ported without regressing GeoMind's base.
- Partial-data rejection with missing-band lists; bounded-parallel SHA-256
  verified downloads with `.partial` rename and staged progress.
- Reflectance scale/offset from STAC `raster:bands`, shared QA-bit validity,
  SCL masking, corrected cloud fraction, batched weather, tiled COGs.

## 2026-11-23 — studio-product-completion

- Unified Landsat 8/9, custom provider registry, gateway-proxied scene
  previews, per-layer RGB band selection, sovereign map sources (ADR 0001),
  CSP, persisted settings, real Ops diagnostics and accessible dialogs.

## 2026-11-23 — product-hardening-and-trust

- Gateway auth/secret handling, retrieval parity and integrity fixes, whole-tree
  lint/type baseline gates and environment-variable alias alignment.
