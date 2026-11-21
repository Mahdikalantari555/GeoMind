# gateway-scene-data — Spec Delta

## ADDED Requirements

### Requirement: ROI scene search

The gateway SHALL expose `POST /api/v1/data/search` accepting
`{roi: GeoJSON polygon geometry, sensor: "landsat"|"sentinel", from: date,
to: date, max_cloud?: number ≤ 100}` and returning `{scenes: [{scene_id,
datetime, cloud_cover, platform, bbox, geometry}]}`, performing the
Planetary Computer STAC search in a threadpool.

- No workspace open → `409 {error.code: "workspace_not_open"}`.
- Invalid sensor or date range → `422 {error.code: "invalid_request"}`.
- Upstream STAC failure → `502 {error.code: "upstream_unavailable"}`.

#### Scenario: search returns scenes for a valid ROI

- **WHEN** a valid polygon ROI and date range are posted
- **THEN** the response lists scene metadata sorted by capture datetime

### Requirement: Scene download job

The gateway SHALL expose `POST /api/v1/data/download` accepting
`{scene_id, roi, sensor, from, to}` and returning `202 {job_id}`. The job
SHALL run the `data_engine.fetch.fetch_scene` facade in a background
thread, emit `job.progress` SSE events with stage/percent as bands land,
persist band files under `<workspace>/data/scenes/<scene_id>/`, register
each band as a workspace raster asset, and complete with
`{scene_id, band_files: {band: relpath}, asset_ids: {band: asset_id}}`.

- Unknown scene id after search → job fails with a typed error message.
- Re-request of a downloaded scene resumes/short-circuits (fetcher-level
  resume), not a duplicate download.

#### Scenario: download job reports progress and completes

- **WHEN** a download is requested for a searched scene
- **THEN** SSE `job.progress` events stream stage transitions and the
  job completes with band file paths and registered asset ids

### Requirement: Raster tile serving

The gateway SHALL expose `GET /api/v1/data/tiles/{z}/{x}/{y}.png`
accepting `path` (workspace-relative raster file) and optional `band`
parameters, reading only files inside the workspace sandbox, rendering
the tile in Web Mercator (EPSG:3857), and returning an image/png
response sized 256×256.

- Path outside sandbox → `403 {error.code: "path_outside_sandbox"}`.
- Missing file or non-raster → `404 {error.code: "file_not_found"}` /
  `422 {error.code: "not_a_raster"}`.
- Out-of-range tiles → `404`.

#### Scenario: tile renders from a downloaded band

- **WHEN** a tile is requested for a workspace-relative band file
- **THEN** a 256×256 PNG of that tile is returned
