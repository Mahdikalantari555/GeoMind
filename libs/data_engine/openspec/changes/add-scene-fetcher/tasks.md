# Tasks: add-scene-fetcher

## 0. Sync with remote (do first)

> **Do NOT re-run this subtree pull over the improved local base.** The
> `sentinel1-and-scene-fetch` change hardened `io/planetary_computer_fetcher.py`
> (lazy `_catalog()`, scene-CRS clipping via `_bounds_in_crs()`, strict typing,
> `min_coverage_ratio=0.9`). A `git subtree pull` would overwrite those fixes;
> diff the two fetcher files instead and port only the needed block.

- [x] 0.1 Pull the GitHub remote into the subtree before any implementation:
      `git subtree pull --prefix=libs/data_engine GeoDataEngine main --squash`
      (a code-changing commit was pushed directly to the GeoDataEngine repo;
      reconcile it with the local tree, run lib tests, and only then start
      work on `fetch`)

## 1. Design groundwork

- [x] 1.1 Offline-first proven via provider-injection fakes instead of
      recorded STAC fixtures (no fixture drift; no live network)
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
- [x] 3.3 Resumability owned by the synced io fetcher (`_find_existing_scene`);
      facade test proves `selected_ids` single-scene pass-through
- [ ] 3.4 Layout compatibility test: fetched scene dir loads via
      `LandsatReader` (deferred — needs a live scene fixture)

## 4. CLI

- [ ] 4.1 Add `data-engine fetch search` / `fetch scene` CLI verbs
      (deferred — gateway routes are the Phase-1 consumer)

## 5. Quality

- [ ] 5.1 Import audit test: no `fetch` imports in domains; no domain/lib
      imports in `fetch`
- [ ] 5.2 Full lib gates green: pytest, ruff, mypy --strict
- [ ] 5.3 README + version bump (0.2.0)
