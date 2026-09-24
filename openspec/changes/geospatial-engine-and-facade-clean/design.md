## Context

Geospatial calculations (NDVI, EVI, NDWI, SAVI, zonal stats, polygonization) are currently implemented in multiple places across `libs/geoagent`, `libs/geomemory`, and `libs/data_engine`. Simultaneously, `geolearn` queries `geomemory.db` via raw SQLite because `GeoMemory` lacks a public method to list candidate memories.

## Goals / Non-Goals

**Goals:**
- Centralize all spectral indices and GIS operations in `data_engine`.
- Make `geoagent.tools.gis_tools` and `geomemory.rs.raster.spectral` consume `data_engine`.
- Expose `GeoMemory.list_candidate_memories` on the public facade and refactor `geolearn` to use it.

**Non-Goals:**
- Modifying the underlying METRIC energy balance equations in `data_engine`.
- Changing candidate memory scoring logic.

## Decisions

### Decision 1: Single Source for Raster Calculations in Data Engine
- **Choice**: Move all index formulas and GIS tools into `data_engine.gis` and `data_engine.surface.vegetation`.
- **Rationale**: `data_engine` is the scientific computing layer. Having `geoagent` implement custom raster math creates duplication and potential precision bugs.

### Decision 2: Typed Facade Query for Candidate Memories
- **Choice**: Add `list_candidate_memories(states=None, min_observed_at=None)` to `GeoMemory`.
- **Rationale**: Preserves the "facade-only consumption" invariant. `geolearn` no longer needs raw `sqlite3.connect()` on foreign databases.

## Risks / Trade-offs

- [Risk] Circular dependency between `geomemory` and `data_engine`. → Mitigation: `geomemory.rs` lazily imports `data_engine` or keeps lightweight fallbacks if `data_engine` is not installed.
