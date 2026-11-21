# Tasks: add-scene-data-gateway

> Bookkeeping note (2026-11-21): all work live-verified end-to-end
> (draw ROI → STAC search → download job → bands → assets → tile render;
> see docs/qa fifth-pass report). Boxes ticked retroactively — the work
> shipped earlier than the bookkeeping. 1.5 is left open on purpose.

## 1. data_engine fetch facade (implements lib change add-scene-fetcher)

- [x] 1.1 `data_engine/fetch/types.py` — `SceneRef`, `FetchProgress`,
      typed errors (`SceneFetchError`, `SceneIntegrityError`,
      `SceneSearchError`)
- [x] 1.2 `data_engine/fetch/api.py` — `stac_search(roi, sensor, from, to,
      max_cloud)` and `fetch_scene(scene_id, roi, sensor, dest,
      progress_cb)` over the io fetchers; provider injection seams
- [x] 1.3 `data_engine/fetch/__init__.py` public exports
- [x] 1.4 Offline tests: fake fetcher objects (search mapping, progress
      delivery, error mapping); no network in suite
- [ ] 1.5 Lib gates: pytest + ruff + mypy --strict; tasks.md of
      `add-scene-fetcher` checked off
      (gates green 2026-11-20 — data_engine 200 passed; left open because
      the `add-scene-fetcher` lib change stays open, re-scoped)

## 2. Gateway routes

- [x] 2.1 `schemas.py`: `SceneSearchRequest`, `SceneDownloadRequest`
      (Pydantic v2, validation)
- [x] 2.2 `routers/data.py`: `POST /data/search` (threadpool, error
      envelope mapping)
- [x] 2.3 `POST /data/download` → 202 job; fetch in threadpool;
      `job.progress` stage/percent per band; register raster assets;
      job result `{scene_id, band_files, asset_ids}`
- [x] 2.4 `GET /data/tiles/{z}/{x}/{y}.png` — sandboxed path, rio-tiler
      windowed read, PNG response
- [x] 2.5 Mount router in `main.py`; extend CORS note; OpenAPI regen

## 3. Gateway tests

- [x] 3.1 search: valid ROI → scenes; invalid sensor/date → 422; fake
      upstream failure → 502; no workspace → 409
- [x] 3.2 download: job lifecycle with fake fetch (progress events seen,
      result carries band_files/asset_ids); re-download short-circuits
- [x] 3.3 tiles: generated tiny GeoTIFF fixture → 256×256 PNG bytes;
      sandbox escape → 403; missing file → 404
- [x] 3.4 Gates: pytest server/tests, ruff, mypy --strict

## 4. Studio wiring

- [x] 4.1 `lib/api.ts`: real `/data/search` + `/data/download` +
      `subscribeJob` on `job.progress`; asset band URLs → tiles route
- [x] 4.2 Demo data behind explicit `VITE_GEOMIND_DEMO=1` only; UI badge
      shows "Demo" when enabled; no silent fallback
- [x] 4.3 Studio unit tests (vitest) for api mapping + demo gating

## 5. Validation

- [x] 5.1 Full gates green: server, data_engine, studio (check+test+build)
- [x] 5.2 Manual: draw ROI → search → download → layer renders on map
