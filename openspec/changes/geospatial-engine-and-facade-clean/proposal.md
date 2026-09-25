## Why

The GeoFoundation codebase suffers from two architectural boundary issues:
1. **Scattered GIS & Spectral Logic**: Spectral indices (NDVI, EVI, NDWI, SAVI), zonal statistics, polygonization, reclassification, and area calculations are duplicated across `geoagent.tools.gis_tools`, `geomemory.rs.raster.spectral`, and `data_engine.surface.vegetation`. This leads to inconsistent formula handling, divergent nodata values, and flawed planar degree-squared area approximations.
2. **Facade Bypass in GeoLearn**: `geolearn/training_pipeline.py` connects directly to `geomemory.db` via raw SQLite to query `candidate_memory`, breaking the fundamental invariant that external libraries must consume only public facades.

Importantly, `docs/ARCHITECTURE.md §3.3` explicitly forbids `geomemory -> data_engine` (*"GeoMemory's rs/ module has its own pure-numpy NDVI/EVI; it does not import data_engine"*). We must not create a direct dependency from `geomemory` to `data_engine`.

Instead, establishing a shared computation library (`libs/geospatial_core`) and exposing typed candidate memory queries on the `geomemory` public facade restores strict architectural layering while eliminating code duplication.

## What Changes

- **Create Shared Core Geospatial Library (`libs/geospatial_core`)**:
  - Centralize spectral index formulas (`ndvi`, `evi`, `ndwi`, `savi`) with uniform float32/float64 and nodata support.
  - Provide pure computational functions for `zonal_stats`, `polygonize`, `reclassify`, geodesic/metric area calculations, and CRS/coordinate helpers.
  - Dependencies: `geomemory -> geospatial_core`, `geoagent -> geospatial_core`, `data_engine -> geospatial_core`.
  - Architecture rule §3.3 is strictly preserved (`geomemory` does NOT import `data_engine`).
- **Thinning GeoAgent and GeoMemory GIS Wrappers**:
  - Update `geoagent.tools.gis_tools` and `geomemory.rs.raster.spectral` to delegate calculations to `geospatial_core`.
  - Remove duplicate private formulas from `geoagent` and `geomemory`.
- **Public Candidate Memory Access in GeoMemory**:
  - Expose `GeoMemory.list_candidate_memories(states: list[str] | None = None, min_observed_at: str | None = None) -> list[CandidateMemory]` in the public facade.
  - Refactor `geolearn.training_pipeline` to query candidate memories exclusively through `GeoMemory` facade calls, eliminating raw SQLite queries against `geomemory.db`.

## Capabilities

### New Capabilities
- `geospatial-core`: Unified scientific GIS and spectral index processing library.

### Modified Capabilities
- `candidate-memory-completion`: Add public facade query methods for candidate memory retrieval.

## Impact

- `libs/geospatial_core`: New shared library for core raster math, spectral indices, and GIS calculations.
- `libs/data_engine`: Re-exports and builds upon `geospatial_core`.
- `libs/geoagent`: `tools/gis_tools.py` delegates to `geospatial_core`.
- `libs/geomemory`: `core/workspace.py` exports `list_candidate_memories()`; `rs/raster/spectral.py` delegates to `geospatial_core` without depending on `data_engine`.
- `libs/geolearn`: `training_pipeline.py` removes raw `sqlite3.connect(geomemory_db)` in favor of facade calls.
