## Context

The server gateway was designed as a thin HTTP facade over geomemory's public API. Over time, several router modules reached into geomemory internals to access functionality that was not yet exposed on the `GeoMemory` facade. This created a tight coupling where geomemory refactors would silently break the server. The same pattern exists for geoagent internal classes (e.g., `Registry`, `PlaybookManager`).

The double `SearchService` issue is a separate but related design seam: `geomemory/services/search_service.py` wraps `geomemory/retrieval/search_service.SearchService` but drops `modalities` and `modality_weight` parameters, while `Workspace.search()` bypasses the wrapper entirely.

## Goals / Non-Goals

**Goals:**
- Expose all server-needed operations on the `GeoMemory` public facade
- Remove all internal imports from `server/src/geofront_api/`
- Unify the SearchService ambiguity
- Ensure geomemorytest black-box suite continues to validate the facade

**Non-Goals:**
- Refactoring geomemory's internal architecture (repository layer, service layer)
- Adding new capabilities beyond what the server currently needs
- Changing the geoagent SDK's public API (that is a separate concern)
- Migrating the web app or server to a different architecture

## Decisions

### D1: Add facade methods rather than re-exporting internals
**Choice**: Create wrapper methods on `Workspace`/`GeoMemory` that delegate to internal classes, rather than re-exporting the internal classes themselves.
**Rationale**: Re-exporting would defeat the purpose — the server would still import internals, just through a different path. Wrapper methods on the facade create a stable contract that can evolve independently.

### D2: Location of new methods — workspace.py
**Choice**: All new facade methods go on the `Workspace` class in `libs/geomemory/src/geomemory/core/workspace.py`, which is already aliased as `GeoMemory` in `__init__.py`.
**Rationale**: This is the canonical public entry point. All existing public operations (search, ask, ingest, etc.) live here. Consistent placement reduces cognitive load.

### D3: Lazy imports inside facade methods
**Choice**: New facade methods SHALL use lazy imports (import inside the function body) for heavy optional dependencies, matching the existing pattern in `workspace.py`.
**Rationale**: Maintains the single-writer, lazy-import philosophy. Heavy deps (geopandas, rasterio) are not imported at module load time.

### D4: Delete the thin SearchService wrapper
**Choice**: Remove `geomemory/services/search_service.py` entirely. All callers should use `geomemory/retrieval/search_service.SearchService` directly or go through `Workspace.search()`.
**Rationale**: The wrapper is unused by `Workspace.search()` and confusing to consumers. Deleting it eliminates the ambiguity with no behavioral change.

## Risks / Trade-offs

- **[Risk] Breaking geomemorytest suite**: If new facade methods are not covered by geomemorytest, the black-box validation weakens. **Mitigation**: Add test cases to `geomemorytest/` for each new method.
- **[Risk] Workspace class bloat**: Adding 7+ methods to `Workspace` increases its size. **Mitigation**: Each method is a thin delegator (~5-10 lines); the class is already 1200+ lines. Acceptable for now; consider splitting into a `WorkspacePublicAPI` mixin later.
- **[Risk] SearchService deletion removes a public entry point**: Some external consumers may use `geomemory.services.search_service.SearchService`. **Mitigation**: This is an alpha v0.1 product; the wrapper was documented as internal-ish. Check for external usage before deleting.

## Migration Plan

1. Add new methods to `Workspace` in `workspace.py`
2. Export any new models from `__init__.py` if needed
3. Update each server router to use facade methods
4. Delete or unify `services/search_service.py`
5. Run `pytest libs/geomemory/tests -q` and `pytest libs/geomemory/geomemorytest/ -q`
6. Run `conda run -n geospatial pytest server/tests -q`
7. Regenerate web API client: `cd apps/web && pnpm gen:api`
