# Tasks: add-scene-fetcher

## 0. Sync with remote (do first)

- [x] 0.1 Pull the GitHub remote into the subtree before any implementation:
      `git subtree pull --prefix=libs/data_engine GeoDataEngine main --squash`
      (a code-changing commit was pushed directly to the GeoDataEngine repo;
      reconcile it with the local tree, run lib tests, and only then start
      work on `fetch`)

## 1. Design groundwork

- [ ] 1.1 Record STAC fixtures (search response + item JSON for one Landsat
      and one Sentinel-2 scene) under `tests/fixtures/stac/` — offline tests
      only, no live network
- [ ] 1.2 Define `SceneRef`, `FetchProgress`, typed exceptions
      (`SceneFetchError`, `SceneIntegrityError`) in `data_engine.fetch.types`

## 2. Search

- [ ] 2.1 Implement `stac_search` (pystac-client + Planetary Computer; bbox,
      datetime range, collections; typed error mapping)
- [ ] 2.2 Unit tests against fixtures: filtering, sorting, typed failures

## 3. Download

- [ ] 3.1 Implement `fetch_scene`: bounded-concurrency asset downloads,
      streaming writes, `.partial` markers, SHA-256 verification, one
      re-fetch on integrity failure
- [ ] 3.2 Implement `progress_cb` protocol with bounded rate; callback
      errors isolated from fetch path
- [ ] 3.3 Resumability: interrupted-run unit test proves only incomplete
      assets re-fetch; final layout identical to uninterrupted run
- [ ] 3.4 Layout compatibility test: fetched scene dir loads via
      `LandsatReader` with standard band structure

## 4. CLI

- [ ] 4.1 Add `data-engine fetch search` and `data-engine fetch scene`
      verbs wired to the same functions (progress to stderr)

## 5. Quality

- [ ] 5.1 Import audit test: no `fetch` imports in domains; no domain/lib
      imports in `fetch`
- [ ] 5.2 Full lib gates green: pytest, ruff, mypy --strict
- [ ] 5.3 README + version bump (0.2.0)
