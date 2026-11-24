# GeoMind — Phase 2 TODO (user-defined GeoAI features)

> Phase 1 (real acquisition loop + training routes + studio wiring) is done
> and tested — see `openspec/changes/add-scene-data-gateway` and
> `openspec/changes/add-studio-training-lab`.
>
> **This list is intentionally app-level:** before each item is built, the
> owner decides the exact application/domain (which crops, which regions,
> which report formats). Nothing here is spec'd yet — each item becomes an
> openspec change when picked up.
>
> **Spine locked 2026-11-21: the data-sovereign agent** — answers cite or
> abstain, data never leaves the machine, feedback becomes training. The
> end criterion is published numbers: see
> `openspec/changes/publish-agent-baseline`. The GeoAI features below serve
> this spine; the METRIC ETa pilot is its demo case study.

## 🔎 GeoAI differentiators (the "real GeoAI" layer)

- [ ] **Vision search on the map** — use the sleeping OlmoEarth/ONNX
      embeddings in `geomemory` (`vision` ingest path + `search_images`) as
      a Studio feature: pick a parcel/tile → "find scenes/tiles similar to
      this". Needs: tiles-to-embedding bridge + a Studio view.
      → headless bridge spike DONE (tile granularity, `scripts/vision_search_spike.py`,
      ADR 0003); Studio view deliberately deferred — see ADR for prerequisites.
      → owner decision: which embedding granularity (scene vs tile)? → tile, per spike.
- [ ] **Change detection & time series per parcel** — NDVI/EVI seasonal
      series from ingested scenes (`geospatial_core` zonal stats exist);
      anomaly alerts when a parcel drops below its seasonal median.
      → owner decision: which index thresholds + alert routing (UI badge?
      agent mention? report?)
- [ ] **Parcel report generator** — one-click PDF per farm/ROI: layer
      snapshots, cited QA answers, ETa/NDVI trend, learned-model prediction
      with confidence. Builds on provenance chain.
      → owner decision: report language (fa/en), branding, delivery channel
- [x] **True-color composite tiles** — stack downloaded bands (red/green/
      blue) into an RGB tile render (extend `_render_tile` or pre-compute a
      composite at download time) so map layers look like imagery, not
      single-band previews. (Composite tile route + Studio RGB editor in
      `studio-product-completion`.)
- [x] **Live agent chat in Studio** — stream the real gateway
      `/agent/chat` (SSE) with tool cards, like `apps/web` already does;
      replace the scripted AgentRail playbook responses. (`ship-and-measure-agent`.)
- [x] **COG optimization post-download** — convert fetched bands to COG
      with overviews so tile serving is fast on large scenes. (`sentinel1-and-scene-fetch`.)

## 🚢 Deliverable/startup hardening

- [ ] **Studio e2e (Playwright)** — the 60-second demo as a test: draw ROI →
      search → download (fake fetcher) → layer renders → ask → cite → train.
- [ ] **Multi-workspace sessions** — implement per
      `openspec/changes/design-multi-workspace-gateway` when the first pilot
      needs two concurrent projects on one gateway.
- [ ] **Packaging & release story** — Docker Hub image for gateway+studio,
      PyPI publishes for the six libs, docs site (CHARTER/VISION as landing).
- [ ] **Demo workspace seeding** — one command that opens a workspace,
      ingests `sample/` data, and prints the demo script.
- [ ] **LLM onboarding flow** — settings probe + local-GGUF download path in
      Studio Settings (models hub is wired server-side already).

## 🧹 Known smaller debts (from the debt paydown session)

- [ ] geomemory: 3 pre-existing Windows test failures (CLI dashboard check,
      lance backend, olmoearth multichannel) — environment-specific.
- [ ] data_engine: `test_init_custom` asserts `/tmp/cache` literal —
      Windows path (pre-existing).
- [ ] geomemory mypy --strict: ~46 pre-existing errors in untouched files
      (CI currently gates on changed-files only) — worth a cleanup change.
- [x] `qa-manual.html` removed from root (legacy GeoFoundation QA manual;
      superseded by `docs/qa/` per-pass reports + `scripts/qa/`; recoverable
      from git history).
- [x] `sample/sasmple.qmd` renamed to `sample/sample.qmd`. NOTE: delivered
      spec `sample-pipeline` still references `sample/sasmple.geojson`, which
      no longer exists — spec drift, fix in a separate change.
- [ ] openspec spec-sync debt: Studio capability deltas were archived
      unsynced (no `studio-*` main specs exist: studio-agent-rail,
      studio-map-layers, studio-frontend, and the superseded svelte app's
      shell/acquire/roi/onboarding) + `app-presentation` delta unsynced
      (frozen web app). Sync in a dedicated change only if Studio contracts
      need spec coverage.
