# Proposal: add-scene-data-gateway

## Why

The Studio Acquire page (change `add-svelte-studio-app`) calls
`POST /data/search`, `POST /data/download`, and map tile URLs that the
gateway does not serve yet — the UI falls back to generated sample data,
so the flagship demo ("draw ROI → download → layer on map") is fake at its
heart. `data_engine` already ships a mature Planetary Computer fetcher
(search + bounded-parallel download + ROI clipping + per-scene resume);
it only needs a typed lib facade and gateway routes.

## What Changes

- **data_engine `fetch` facade** (lib change `add-scene-fetcher`, this
  change implements it): `data_engine.fetch` subpackage exposing
  `stac_search(...)` and `fetch_scene(...)` over the existing
  `io.planetary_computer_fetcher` classes — typed `SceneRef` results,
  `FetchProgress` callback protocol, typed errors, provider injection for
  offline tests. Gateway consumes only this public facade.
- **Gateway `POST /api/v1/data/search`** — `{roi (GeoJSON polygon),
  sensor: "landsat"|"sentinel", from, to, max_cloud}` → `{scenes:
  SceneRef[]}` (blocking facade call in threadpool).
- **Gateway `POST /api/v1/data/download`** — `{scene_id, roi, sensor,
  from, to}` → `202 {job_id}`; job downloads the scene into the
  workspace data dir (`data/scenes/<scene_id>/`), emits `job.progress`
  (stage = band index) over the existing SSE bus, and registers each band
  as a workspace raster asset so the provenance chain applies.
- **Gateway `GET /api/v1/data/tiles/{z}/{x}/{y}.png`** — sandboxed
  workspace-relative raster path (+ optional band selection), windowed
  read via rio-tiler, Web-Mercator PNG response for MapLibre raster
  sources. No external tile server; single-box deployments stay intact.
- **OpenAPI regeneration** so `apps/web` `pnpm gen:api` picks the new
  routes; Studio `api.ts` switches to the real routes with an explicit,
  labeled Demo Mode fallback (no silent fakes).

## Capabilities

### New Capabilities
- `gateway-scene-data` — ROI scene search, download jobs with progress,
  and raster tile serving through the gateway.

## Impact

- **data_engine:** new `fetch/` subpackage + tests (offline, provider
  injection); version intent 0.2.0.
- **server:** new `routers/data.py` (+ schemas, tests), rio-tiler dep.
- **apps/studio:** `lib/api.ts` real routes; acquire/map views wired;
  demo data moves behind an explicit `VITE_GEOMIND_DEMO=1` flag.
- **Tests:** server tests fake the fetch facade (no network); tile tests
  use a generated tiny GeoTIFF fixture.

## Dependencies

- Builds on `add-svelte-studio-app` (job progress plumbing, SSE) and the
  synced `planetary_computer_fetcher` (resumable, ROI-clipped downloads).
- Unblocks `integrate-studio-frontend` connectivity tasks and
  `add-studio-training-lab` § 2/3 (same job/progress machinery).

## Out of Scope

- COG optimization of fetched scenes (rio-tiler serves plain GeoTIFFs;
  COG conversion is a later data_engine change).
- Providers beyond Planetary Computer; authentication of any kind.
