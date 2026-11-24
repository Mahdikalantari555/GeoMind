# Tasks — sentinel1-and-scene-fetch

Verification gate (`2026-11-24`): `cd libs/data_engine && conda run -n geo pytest -q && conda run -n geo ruff check src` — both green (230 passed; ruff clean). `conda run -n geo mypy --strict src/` remains red on pre-existing typing debt: 687 errors across 43 files, down from 688 at base HEAD. This change introduces **zero new mypy errors** (all ported/existing-touched code is strictly typed); the lib was never mypy-clean. Full lib-wide mypy-green is separate tech debt, out of scope here. The proposal requires strict typing of the new code, not a green whole-lib gate.

## 0. Guard rail

- [x] 0.1 Do NOT `git subtree pull` over the improved base. Diff the two
      fetcher files and confirm GeoMind's `_catalog()` (`:193`),
      `_bounds_in_crs()` (`:734`), scene-CRS clipping and `min_coverage_ratio=0.9`
      are untouched by the port.

## 1. Sentinel-1 port (A-004)

- [x] 1.1 Append the S1 constants + `_configure_gdal_http` +
      `Sentinel1PlanetaryComputerFetcher` + `Sentinel1RtcPlanetaryComputerFetcher`
      from GeoDataEngine `io/planetary_computer_fetcher.py:1278-1878`, adding
      `Any`/`Literal` annotations for strict mypy. (P0-1)
- [x] 1.2 Add the `BAND_MAPPING` class hook to the Landsat/S2/S1 classes and
      switch `__init__` validation to `self.BAND_MAPPING`. (P0-2)
- [x] 1.3 Re-export both S1 fetchers from `io/__init__.py`. (P0-3)
- [x] 1.4 Add `"sentinel-1"`/`"sentinel-1-rtc"` to `SENSORS` and `_build_fetcher`. (P0-4)
- [x] 1.5 Make `cloud_cover` optional on `SceneRef`/`FetchResult` with a
      `cloud_available` flag; preserve `None` through `scenes_from_rows`. (P0-6)
- [x] 1.6 Guard the `None` datetime sort key and scope `_find_existing_scene`
      to `MTL*.json` when porting. (do-not-port defects 5, 7)
- [x] 1.7 Port GeoDataEngine tests `:428-828` offline; add facade tests for
      `_build_fetcher("sentinel-1")` and cloud mapping. (P1-7)
- [x] 1.8 Declare GDAL/`osgeo` in `pyproject.toml`; keep the graceful
      `DownloadError` install hint. (P2-11)

## 2. Fetch robustness (D-036…D-049)

- [x] 2.1 Validate required band set before returning; raise `PartialDataError`
      with the missing bands; delete partial files. (D-036)
- [x] 2.2 Bounded-parallel per-asset downloads (max 4), SHA-256 verify,
      `.partial` + atomic rename, `fetch`/`verify` progress events. (D-037)
- [x] 2.3 Align search/download coverage policy; add `coverage` metadata if
      partial scenes remain searchable. (D-038)
- [x] 2.4 Stable scene-id suffix in Sentinel directory names; reuse
      `_find_existing_scene` in the Sentinel override. (D-039, D-040)
- [x] 2.5 Honour `resolution` via `out_shape`/`window_transform` (nearest for
      QA/SCL); add per-band retry/timeout with re-signing. (D-045, D-046)
- [x] 2.6 Replace `arr > 0` coverage heuristic with raster masks/nodata + QA;
      stop mutating `PROJ_LIB`/numpy/pandas at import time. (D-047, D-048)
- [x] 2.7 Remove the broad `except → 0` in `get_scene_count`; suppress only
      `OSError` (not `BaseException`) in cleanup; close the STAC client via a
      context manager; raise on a missing scene date instead of returning the
      hardcoded 2023-04-27 fallback, and fix the dead `if not mtl_path` check. (D-049, weather-date appendix)
- [x] 2.8 Batch weather requests; write tiled COGs with overviews. (P-076, P-077)
- [x] 2.9 Offline rasterio-windowing test with a small georeferenced TIFF
      asserting bounds/dtype/nodata and coverage rejection. (T-083)

## 3. Physics inputs (D-041…D-044)

- [x] 3.1 Persist STAC `raster:bands` scale/offset in MTL; apply
      `data * scale + offset` for non-QA bands; DN→reflectance regression test. (D-041)
- [x] 3.2 Expose one `CloudMasker` validity helper; replace the four duplicated
      bit expressions in `vegetation/albedo/emissivity/roughness`. (D-042)
- [x] 3.3 Fix the inverted cloud-coverage metric; add an SCL masker and wire
      `qa60`/`scl` into the pipeline. (D-043, D-044)
- [x] 3.4 Validate all changes against `test_calibration_physical_values.py`.

## 4. Release

- [x] 4.1 Update `add-scene-fetcher/spec.md:15-16` to include S1 collections;
      add a note at `tasks.md:3-9` not to subtree-pull over the improved base.
- [x] 4.2 Version bump (`0.2.0`) + README `[sar]` extra / S1 docs; gates recorded
      in the gate note above (pytest 230 passed, ruff clean, mypy 0 new errors —
      687 pre-existing across 43 files vs 688 at base; whole-lib mypy green is
      out-of-scope tech debt).
