# scene-fetch — Spec Delta

## MODIFIED Requirements

### Requirement: Supported sensors

The fetch facade SHALL support `landsat`, `sentinel` (Sentinel-2) and
`sentinel-1`, with `sentinel-1-rtc` as a selectable RTC variant. Sentinel-1
SHALL query `sentinel-1-grd` (or `sentinel-1-rtc`) with vv/vh polarizations and
SHALL NOT report a cloud-cover value (SAR is cloud-independent). Scene
directories SHALL be named `sentinel1_<date>_<asc|desc>` and SHALL be resumable.

#### Scenario: Sentinel-1 scene search
- **WHEN** `stac_search(..., sensor="sentinel-1")` is called for a valid ROI
- **THEN** results carry `cloud_available=False` and SAR descriptors
  (polarizations, instrument mode, orbit state)

#### Scenario: same-date Sentinel-1 passes do not collide
- **WHEN** an ascending and a descending GRD scene share an acquisition date
- **THEN** they are written to distinct directories and neither band set is overwritten

### Requirement: Download integrity and progress

Downloads SHALL use bounded parallelism (default 4), verify SHA-256 per asset,
write each asset to `.partial` then atomically rename, and emit `search/fetch/
verify/done` progress stages with per-asset detail. A scene missing any required
band SHALL fail with `PartialDataError` listing the missing bands; it SHALL NOT
be registered as a completed download. Catalog failures SHALL propagate as typed
errors, not become "0 scenes".

#### Scenario: one band fails to download
- **WHEN** one of eight Landsat band requests fails after retries
- **THEN** `fetch_scene` raises `PartialDataError` and no partial asset set is registered

### Requirement: Search/download coverage parity

Search results SHALL be downloadable under the same coverage policy used by the
download path, or SHALL carry a `coverage: full|partial` field that lets the
caller make an informed choice. The requested `resolution` SHALL be honoured via
windowed reads with a matching output transform; QA/SCL bands SHALL use
nearest-neighbour resampling.

### Requirement: Scientifically usable band values

Downloaded reflectance bands SHALL carry STAC `raster:bands` scale/offset in
metadata and the reader SHALL apply `data * scale + offset` for non-QA bands.
Cloud/shadow masking SHALL use one shared QA-bit helper (dilated=1, cloud=3,
shadow=4) across all surface modules, and Sentinel scenes SHALL be masked via an
SCL-based masker. The METRIC cloud-coverage metric SHALL report the cloud
fraction (clear pixels are not clouds). Downloaded rasters SHALL be tiled COGs
with overviews.
