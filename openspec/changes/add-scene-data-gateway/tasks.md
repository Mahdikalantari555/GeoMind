# Tasks: add-scene-data-gateway

## 1. data_engine fetch facade (implements lib change add-scene-fetcher)

- [ ] 1.1 `data_engine/fetch/types.py` — `SceneRef`, `FetchProgress`,
      typed errors (`SceneFetchError`, `SceneIntegrityError`,
      `SceneSearchError`)
- [ ] 1.2 `data_engine/fetch/api.py` — `stac_search(roi, sensor, from, to,
      max_cloud)` and `fetch_scene(scene_id, roi, sensor, dest,
      progress_cb)` over the io fetchers; provider injection seams
- [ ] 1.3 `data_engine/fetch/__init__.py` public exports
- [ ] 1.4 Offline tests: fake fetcher objects (search mapping, progress
      delivery, error mapping); no network in suite
- [ ] 1.5 Lib gates: pytest + ruff + mypy --strict; tasks.md of
      `add-scene-fetcher` checked off

## 2. Gateway routes

- [ ] 2.1 `schemas.py`: `SceneSearchRequest`, `SceneDownloadRequest`
      (Pydantic v2, validation)
- [ ] 2.2 `routers/data.py`: `POST /data/search` (threadpool, error
      envelope mapping)
- [ ] 2.3 `POST /data/download` → 202 job; fetch in threadpool;
      `job.progress` stage/percent per band; register raster assets;
      job result `{scene_id, band_files, asset_ids}`
- [ ] 2.4 `GET /data/tiles/{z}/{x}/{y}.png` — sandboxed path, rio-tiler
      windowed read, PNG response
- [ ] 2.5 Mount router in `main.py`; extend CORS note; OpenAPI regen

## 3. Gateway tests

- [ ] 3.1 search: valid ROI → scenes; invalid sensor/date → 422; fake
      upstream failure → 502; no workspace → 409
- [ ] 3.2 download: job lifecycle with fake fetch (progress events seen,
      result carries band_files/asset_ids); re-download short-circuits
- [ ] 3.3 tiles: generated tiny GeoTIFF fixture → 256×256 PNG bytes;
      sandbox escape → 403; missing file → 404
- [ ] 3.4 Gates: pytest server/tests, ruff, mypy --strict

## 4. Studio wiring

- [ ] 4.1 `lib/api.ts`: real `/data/search` + `/data/download` +
      `subscribeJob` on `job.progress`; asset band URLs → tiles route
- [ ] 4.2 Demo data behind explicit `VITE_GEOMIND_DEMO=1` only; UI badge
      shows "Demo" when enabled; no silent fallback
- [ ] 4.3 Studio unit tests (vitest) for api mapping + demo gating

## 5. Validation

- [ ] 5.1 Full gates green: server, data_engine, studio (check+test+build)
- [ ] 5.2 Manual: draw ROI → search → download → layer renders on map
