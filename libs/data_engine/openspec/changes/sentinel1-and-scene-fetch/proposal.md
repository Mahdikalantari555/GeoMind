# Proposal: sentinel1-and-scene-fetch

> Lib-level change. Lives in `libs/data_engine/openspec/changes/` per the
> per-lib ownership rule (root AGENTS.md). Merges the Sentinel-1 port with the
> fetch-robustness and physics-input correctness findings.

## Why

The user added Sentinel-1 support in the separate `D:\RS\Projects\GeoDataEngine`
project and wants it brought into GeoMind. GeoMind's `fetch/api.py:24` has
`SENSORS = ("landsat","sentinel")`; the gateway enum, agent tool enum and Studio
sensor list all exclude S1. GeoDataEngine has a complete implementation at
`.../io/planetary_computer_fetcher.py:1278-1878` (GRD `sentinel-1-grd` + RTC
`sentinel-1-rtc`, vv/vh polarizations, `sentinel1_<date>_<orbit>` directories,
GDAL TPS geolocation, no cloud cover).

**Critical constraint:** the two files are near-identical forks that diverged
in opposite directions. GeoMind's base has the CRS-window fix (`_bounds_in_crs`
`,734`), lazy `_catalog()` (`:193`) and strict typing; GeoDataEngine's older
base dropped all three and changed `min_coverage_ratio` 0.9 → 1/0.55. Port **only
the S1 block**, never copy the file — copying would regress three fixed bugs.

The same fetch path has correctness gaps the audit flagged: incomplete scenes
are reported as successful (`:618,1099`), downloads are sequential with no
checksums/`.partial` resume/staged progress despite the spec mandating them,
search and download use different coverage rules, same-date Sentinel tiles
overwrite each other, `resolution` is ignored, reflectance scaling is never
applied, cloud QA bits are wrong in four surface modules, and the METRIC cloud
coverage metric is inverted.

## What Changes

**Sentinel-1 port:**
- Append the S1 block (constants, `_configure_gdal_http`,
  `Sentinel1PlanetaryComputerFetcher`, `Sentinel1RtcPlanetaryComputerFetcher`)
  to GeoMind's fetcher, adapted to strict typing and keeping GeoMind's base
  intact. Add the `BAND_MAPPING` class hook required for `bands=["vv","vh"]`.
- Re-export both S1 fetchers from `io/__init__.py`; add `"sentinel-1"` and
  `"sentinel-1-rtc"` to `SENSORS` and `_build_fetcher`.
- Make `cloud_cover` optional on `SceneRef`/`FetchResult` with a
  `cloud_available` flag (SAR has no cloud property) — do not fabricate 0 %.
  Widen the gateway `Literal`/enum (coordinated in
  `studio-product-completion`, which also adds the Studio option and fixes the
  band heuristic from B02/B03/B04/B08 to vv/vh).
- Port the mocked offline tests from GeoDataEngine; guard the `None` datetime
  sort key; scope `_find_existing_scene` to `MTL*.json`.

**Fetch robustness:**
- Reject partial scenes: validate downloaded bands against the required set
  and raise `PartialDataError` with the missing list.
- Implement bounded-parallel downloads with per-asset `ThreadPoolExecutor`
  (max 4), SHA-256 verification, `.partial` + atomic rename, and `fetch`/`verify`
  progress events — or formally descope the open spec items.
- Align search/download coverage policy; include a stable scene-id suffix in
  Sentinel directory names; make Sentinel resumable; honour `resolution` via
  `out_shape`/`window_transform`; add per-band retry/timeout with re-signing;
  use raster masks/nodata instead of the `arr > 0` heuristic; scope GDAL HTTP
  config and stop deleting `PROJ_LIB` at import time.
- Batch weather requests; write tiled COGs with overviews.
- Add an offline rasterio-windowing test with a small local GeoTIFF fixture.

**Physics inputs:**
- Persist STAC `raster:bands` scale/offset and apply `data * scale + offset`
  for non-QA bands; add a DN→reflectance regression test.
- Replace the four duplicated wrong QA-bit expressions with one shared helper
  from `CloudMasker`.
- Fix the inverted cloud-coverage metric; add a Sentinel SCL-based masker and
  wire `qa60`/`scl` into the pipeline.

## Capabilities

### Modified Capabilities
- `scene-fetch` — adds Sentinel-1 GRD/RTC, integrity checks, resume, parallel
  downloads, staged progress, honest partial-scene reporting.
- `data-engine-gis` — correct reflectance scaling, QA masks and cloud coverage.

## Impact

- **data_engine:** `io/planetary_computer_fetcher.py` (append-only for S1 plus
  targeted base fixes), `io/__init__.py`, `fetch/{api,types}.py`, tests,
  `pyproject.toml` (declare GDAL/`osgeo`), version bump.
- **Gateway/Studio:** enum widening and S1 option live in
  `studio-product-completion`; this lib change supplies the capability.
- **Physics outputs will change (correctly)** — validate against the existing
  `test_calibration_physical_values.py` harness.

## Dependencies

- No lib changes outside `data_engine`.
- Studio/gateway enum widening depends on this change landing first (or in the
  same release train). Do NOT run the `git subtree pull` at
  `add-scene-fetcher/tasks.md:3-9` — it would overwrite the improved base.

## Out of Scope

- Implementing `SentinelPipeline` (currently a permanent stub) — document
  Sentinel as acquisition-only or open a separate change.
- Reprojecting downloaded bands to a guessed UTM (GeoDataEngine regressed this);
  keep GeoMind's scene-CRS clipping.
- METRIC energy-balance physics beyond band/QA/nodata/scaling inputs.

## Findings covered

A-004, D-036…D-049, P-076, P-077, T-083, TECHDEBT-01/02,
data_engine CORRECTNESS-01/02, plus the porting checklist items P0-1…P2-12.
