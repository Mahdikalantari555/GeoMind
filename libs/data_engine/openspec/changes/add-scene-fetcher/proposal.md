# Proposal: add-scene-fetcher

> Lib-level change. Lives in `libs/data_engine/openspec/changes/` per the
> per-lib openspec ownership rule (AGENTS.md).

## Why

GeoMind Studio's Acquire page needs to search and download satellite scenes
for a user-drawn ROI, and no scene-acquisition capability exists anywhere
today (the envisioned ` planetary_computer_fetcher` was never built). The
user decision: acquisition is a `data_engine` capability, implemented inside
the lib as a new `fetch` subpackage — keeping the lib the single home for
"get data in, compute physics out".

## What Changes

- Add `data_engine.fetch` subpackage:
  - `stac_search(bbox, datetime, collections)` → `SceneRef` list (id, date,
    cloud cover, geometry, asset URLs) via the Microsoft Planetary Computer
    STAC API (no API key).
  - `fetch_scene(scene_ref, dest, *, progress_cb=None, concurrency=4)` →
    downloaded asset files with bounded parallel asset fetches, streaming
    writes (no temp-file duplication), SHA-256 integrity check per asset.
  - Per-asset resumability: partial downloads tracked with `.partial`
    markers; a retried fetch resumes incomplete assets only.
  - Local dataset layout documented (band files + metadata JSON under
    `<dest>/<scene_id>/`), compatible with existing `LandsatReader` /
    Sentinel preprocessing inputs.
- Thin CLI verbs: `data-engine fetch search` / `fetch scene`.
- No changes to existing physics modules; no imports from the new subpackage
  into existing domains (Landsat ↔ Sentinel separation untouched).

## Capabilities

### New Capabilities
- `scene-fetch` — STAC search + resumable, progress-reporting scene
  download.

## Impact

- **data_engine:** new subpackage + deps (`pystac-client`, `httpx` — both
  pure-Python-friendly); version minor bump.
- **Consumers:** gateway download job (root change `add-svelte-studio-app`)
  calls this through a threadpool job and forwards `progress_cb` into
  `job.progress` reporting.
- **Tests:** offline unit tests with recorded STAC JSON fixtures — no live
  network in the test suite (restricted-network friendly).

## Dependencies

- **Remote sync first:** the GeoDataEngine GitHub repo has a direct
  code-changing commit not yet in this tree. The `0.x` task in `tasks.md`
  requires `git subtree pull --prefix=libs/data_engine GeoDataEngine main
  --squash` (reconcile + lib tests green) before any implementation.
- The gateway download job (root change `add-svelte-studio-app`) waits on
  this capability; until it lands, the Acquire page shows its designed
  empty state.

## Out of Scope

- Providers beyond Planetary Computer (generic STAC URLs, keys, GEE).
- COG conversion/tiling (handled by existing preprocess/output paths).
- Any agent/memory/learning concern (lib non-goals unchanged).
