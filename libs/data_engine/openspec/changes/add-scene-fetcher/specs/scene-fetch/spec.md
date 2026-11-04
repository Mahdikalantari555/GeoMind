# scene-fetch

## Purpose

Define scene acquisition for `data_engine`: STAC search on the Microsoft
Planetary Computer catalog and resumable, progress-reporting downloads of
scene assets. Input surface for the METRIC/Sentinel pipelines; leaf-lib
boundaries unchanged.

## ADDED Requirements

### Requirement: STAC scene search
The library SHALL expose `stac_search(bbox, datetime_range, collections)`
returning `SceneRef` records (scene id, collection, acquisition datetime,
cloud cover, geometry, asset URLs) for Landsat 8/9 Collection-2 Level-2 and
Sentinel-2 L2A on the Planetary Computer STAC API. Search SHALL require no
API key. Network failures SHALL raise typed errors rooted at the existing
data_engine exception hierarchy — never bare `requests`/`httpx` exceptions.

#### Scenario: Search by ROI and dates
- **WHEN** a search runs for a bbox, date range, and the Landsat collection
- **THEN** matching `SceneRef`s return with id, date, cloud cover, and
  geometry, sorted by acquisition date

#### Scenario: Network failure
- **WHEN** the STAC API is unreachable
- **THEN** a typed fetch error is raised with cause and no partial results

### Requirement: Resumable scene download
`fetch_scene` SHALL download all scene assets with bounded concurrency
(default 4), streaming each asset to disk. Each completed asset SHALL be
checksum-verified (SHA-256 of bytes vs. catalog checksum when provided).
Partial state SHALL be tracked per asset with `.partial` markers; a retried
fetch SHALL resume only incomplete assets and SHALL NOT re-download
completed, verified assets.

#### Scenario: Interrupted download resumes
- **WHEN** a fetch is interrupted after 2 of 5 assets complete, then rerun
  on the same destination
- **THEN** only the 3 incomplete assets are fetched and the final layout is
  identical to an uninterrupted run

#### Scenario: Corrupt asset detected
- **WHEN** a downloaded asset fails checksum verification
- **THEN** the asset is re-fetched (once) before the fetch fails with a
  typed integrity error

### Requirement: Progress reporting
`fetch_scene` SHALL accept a `progress_cb(stage, percent, detail)` callback
invoked on stage transitions and at a bounded rate for byte progress. Stages
SHALL cover: `search` (n/a), `fetch` (per-asset), `verify`, `done`. The
callback SHALL never raise into the fetch path.

#### Scenario: Progress callback sequence
- **WHEN** a scene with 5 assets downloads
- **THEN** the callback reports percent monotonically increasing to 100 with
  per-asset stage details

### Requirement: Local dataset layout compatibility
Downloaded scenes SHALL be laid out under `<dest>/<scene_id>/` with band
files, metadata JSON (scene id, collection, datetime, checksums), and be
directly loadable by the existing `LandsatReader` / Sentinel preprocessing
inputs with no adapter code.

#### Scenario: Downloaded scene loads in pipeline
- **WHEN** a fetched Landsat scene path is passed to `LandsatReader`
- **THEN** it loads and produces the same band structure as a
  manually-provided scene directory

### Requirement: No upward or cross-domain coupling
The `fetch` subpackage SHALL import nothing from `landsat/`, `sentinel/`
domain code or any platform library; domain packages SHALL NOT import
`fetch`. It SHALL depend only on its own shared modules, `pystac-client`,
`httpx`, and the stdlib.

#### Scenario: Import audit
- **WHEN** imports are scanned across the package
- **THEN** `fetch` has no domain imports and domains have no `fetch` imports
