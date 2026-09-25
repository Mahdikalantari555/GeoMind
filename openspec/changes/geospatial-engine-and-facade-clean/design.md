## Context

Geospatial calculations (NDVI, EVI, NDWI, SAVI, zonal stats, polygonization) are currently implemented in multiple places across `libs/geoagent`, `libs/geomemory`, and `libs/data_engine`. Simultaneously, `geolearn` queries `geomemory.db` via raw SQLite because `GeoMemory` lacks a public method to list candidate memories.

Furthermore, `docs/ARCHITECTURE.md §3.3` forbids `geomemory -> data_engine`. Creating a direct dependency between them would violate documented architecture.

## Goals / Non-Goals

**Goals:**
- Create `libs/geospatial_core` containing canonical implementations of spectral indices and GIS algorithms.
- Preserve `docs/ARCHITECTURE.md §3.3` (no direct `geomemory -> data_engine` dependency).
- Make `geomemory.rs.raster.spectral`, `geoagent.tools.gis_tools`, and `data_engine` consume `geospatial_core`.
- Expose `GeoMemory.list_candidate_memories` on the public facade and refactor `geolearn` to use it.

**Non-Goals:**
- Modifying the underlying METRIC energy balance equations in `data_engine`.
- Changing candidate memory scoring logic.

## Decisions

### Decision 1: Shared `libs/geospatial_core` Library
- **Choice**: Place shared raster math, spectral index formulas, and GIS helpers in `libs/geospatial_core`.
- **Rationale**: Keeps `data_engine` independent as the high-level remote-sensing pipeline library while allowing `geomemory` and `geoagent` to share pure computational GIS routines without breaking §3.3.

### Decision 2: Dependency Direction
- **Choice**:
  ```text
  geomemory   ──▶ geospatial_core
  geoagent    ──▶ geospatial_core
  data_engine ──▶ geospatial_core
  ```
  Strictly avoiding `geomemory ──▶ data_engine`.
- **Rationale**: Preserves minimal runtime overhead and independent deployability of each library.

### Decision 3: Typed Facade Query for Candidate Memories
- **Choice**: Add `list_candidate_memories(states=None, min_observed_at=None)` to `GeoMemory`.
- **Rationale**: Preserves the "facade-only consumption" invariant. `geolearn` no longer needs raw `sqlite3.connect()` on foreign databases.

## Risks / Trade-offs

- [Risk] Extra package to maintain in monorepo. → Mitigation: `geospatial_core` is focused strictly on algorithmic and numerical functions with stable interfaces and fast test execution.
