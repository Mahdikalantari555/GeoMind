## Why

The GeoFoundation codebase suffers from two severe architectural boundary violations identified in the architectural audit:
1. **Scattered GIS & Spectral Logic**: Spectral indices (NDVI, EVI, NDWI, SAVI), zonal statistics, polygonization, reclassification, and area calculations are duplicated across `geoagent.tools.gis_tools`, `geomemory.rs.raster.spectral`, and `data_engine.surface.vegetation`. This leads to inconsistent formula handling, divergent nodata values, and flawed planar degree-squared area approximations.
2. **Facade Bypass in GeoLearn**: `geolearn/training_pipeline.py` connects directly to `geomemory.db` via raw SQLite to query `candidate_memory`, breaking the fundamental invariant that external libraries must consume only public facades.

Consolidating all geospatial computation into `data_engine` and adding typed candidate memory queries to the `geomemory` public facade restores strict architectural layering.

## What Changes

- **Consolidate Geospatial Operations in Data Engine**:
  - Centralize spectral index formulas (`NDVI`, `EVI`, `NDWI`, `SAVI`) in `data_engine.surface.vegetation` with uniform float32/float64 and nodata support.
  - Create a dedicated `data_engine.gis` module housing `zonal_stats`, `polygonize`, `reclassify`, geodesic/metric area calculations, and CRS transformations.
- **Thinning GeoAgent and GeoMemory GIS Wrappers**:
  - Update `geoagent.tools.gis_tools` and `geomemory.rs.raster.spectral` to delegate all calculations to `data_engine`.
  - Remove duplicate private formulas from `geoagent`.
- **Public Candidate Memory Access in GeoMemory**:
  - Expose `GeoMemory.list_candidate_memories(states: list[str] | None = None, min_observed_at: str | None = None) -> list[CandidateMemory]` in the public facade.
  - Refactor `geolearn.training_pipeline` to query candidate memories exclusively through `GeoMemory` facade calls, eliminating raw SQLite queries against `geomemory.db`.

## Capabilities

### New Capabilities
- `data-engine-gis`: Unified scientific GIS and spectral index processing engine.

### Modified Capabilities
- `candidate-memory-completion`: Add public facade query methods for candidate memory retrieval.

## Impact

- `libs/data_engine`: Adds `data_engine.gis` and extends `surface/vegetation.py`.
- `libs/geoagent`: `tools/gis_tools.py` becomes a thin registration wrapper over `data_engine`.
- `libs/geomemory`: `core/workspace.py` exports `list_candidate_memories()`; `rs/raster/spectral.py` delegates to `data_engine`.
- `libs/geolearn`: `training_pipeline.py` removes raw `sqlite3.connect(geomemory_db)`.
