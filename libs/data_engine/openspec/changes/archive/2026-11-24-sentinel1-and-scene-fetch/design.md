## Context

Sentinel-1 support was developed in a separate fork
(`D:\RS\Projects\GeoDataEngine`) but that fork diverged from GeoMind's hardened
base in the opposite direction: it dropped the lazy `_catalog()` opener, the
scene-CRS `_bounds_in_crs()` clipping, and strict typing, and changed
`min_coverage_ratio` from `0.9` to `1`/`0.55`. Copying the fork's fetcher over
GeoMind's would have regressed three fixed bugs. The same path also carried
audit findings (A-004, D-036…D-049, P-076/077, T-083): incomplete scenes
reported as success, sequential downloads with no checksum/`.partial`/staged
progress, mismatched search-vs-download coverage rules, same-date Sentinel tile
collisions, ignored `resolution`, unapplied reflectance scaling, wrong QA bits
in four surface modules, and an inverted METRIC cloud-coverage metric.

## Goals / Non-Goals

**Goals:**

- Port only the S1 GRD/RTC block into `io/planetary_computer_fetcher.py`,
  adapted to strict typing, preserving GeoMind's improved base.
- Expose S1 through the fetch facade (`SENSORS`, `_build_fetcher`, `io/__init__`)
  without fabricating a cloud-cover value.
- Make downloads integrity-checked, resumable, bounded-parallel and
  progress-reporting; reject partial scenes with a typed error.
- Correct reflectance scaling, QA/SCL masking and the METRIC cloud metric.

**Non-Goals:**

- Reprojecting bands to a guessed UTM (the fork regressed this) — keep
  scene-CRS clipping.
- Implementing `SentinelPipeline` (a permanent stub) — S1 is acquisition-only.
- METRIC energy-balance physics beyond band/QA/nodata/scaling inputs.
- Fixing the 687 pre-existing whole-lib mypy errors — separate tech debt.

## Decisions

### D1: Append-only S1 port, never copy the fork file

Port only the S1 constants, `_configure_gdal_http`,
`Sentinel1PlanetaryComputerFetcher` and `Sentinel1RtcPlanetaryComputerFetcher`
(`GeoDataEngine:1278-1878`). GeoMind's `_catalog()` (`:193`),
`_bounds_in_crs()` (`:734`), scene-CRS clipping and `min_coverage_ratio=0.9`
remain untouched. Guard rail 0.1 verifies this by diff.

### D2: Strict typing on all ported/touched code

Annotate the S1 block with `Any`/`Literal` so it introduces zero new mypy
errors. The lib was never mypy-clean (688 errors at base, 687 after), so the
gate is "no new errors" plus green `pytest` and `ruff`, not whole-lib green.

### D3: Honest SAR cloud semantics

`SceneRef`/`FetchResult.cloud_cover` becomes optional with a `cloud_available`
flag; SAR reports `None`/`False` rather than a fabricated 0 %. The facade maps
vv/vh to RGB with no invented cloud percentage.

### D4: `BAND_MAPPING` class hook

Each Landsat/S2/S1 fetcher declares its required bands; `__init__` validates
against `self.BAND_MAPPING`. S1 declares `("vv", "vh")`. A missing band is a
`PartialDataError` at the io layer, mapped to `SceneIntegrityError` by the
facade — never a registered "completed" download.

### D5: Bounded-parallel, verifiable, resumable downloads

Per-asset workers capped at 4; each asset streams to `.partial`, is SHA-256
verified against a `.bands.sha256.json` manifest, then atomically renamed.
Retries re-sign asset URLs. Progress is staged `search/fetch/verify/done` with
per-asset detail. Safe scene-id suffixes keep same-date ascending/descending
passes in distinct directories.

### D6: Real coverage, not `arr > 0`

Coverage uses rasterio masks/nodata and `CloudMasker.valid_from_qa` /
`valid_from_scl`. Scrutinised with SCL clear classes `{4,5,6,7}` (masked
`{0,1,3,8,9,10,11}`) so valid vegetation/water pixels are not discarded
(ESA SCL caveat noted). Import-time mutation of `PROJ_LIB`, numpy and pandas
was removed.

### D7: One shared validity helper

The four duplicated QA-bit expressions in `vegetation/albedo/emissivity/
roughness` now call `CloudMasker.valid_from_qa`. The inverted cloud-coverage
metric reports cloud fraction; `qa60`/`scl` are wired into the METRIC pipeline.

### D8: Apply STAC band scaling

`raster:bands` scale/offset are persisted in the scene MTL and applied as
`data * scale + offset` for non-QA bands in `LandsatReader`, with a
DN-to-reflectance regression test.

## Risks / Trade-offs

- **Physics outputs change (correctly)** — scaling/mask fixes alter values;
  validated against `test_calibration_physical_values.py`.
- **SCL class selection is conservative** — avoids data loss but may retain
  some marginal pixels; documented caveat.
- **Gateway/Studio enum widening is coordinated in `studio-product-completion`**
  — this lib change supplies the capability only.
- **Sync deferred** — `scene-fetch` has no lib-level main spec and the base
  ADDED requirements live in the still-in-progress `add-scene-fetcher` change,
  so the delta stays in the archived folder until that change lands.

## Verification

`cd libs/data_engine && conda run -n geo pytest -q` (230 passed) and
`conda run -n geo ruff check src` (clean). `mypy --strict src/` adds zero new
errors; see `tasks.md` gate note.
