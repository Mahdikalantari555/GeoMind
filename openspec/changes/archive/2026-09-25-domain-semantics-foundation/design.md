## Context

Currently, entity IDs, timestamps, and classification labels are defined ad-hoc across libraries as unstructured strings. This causes ownership drift where the same farm or observation cannot be traced across GeoMemory, GeoAgent, and GeoLearn.

## Goals / Non-Goals

**Goals:**
- Create `libs/geodomain` as a standalone, pure domain library (Pydantic v2 domain types and contracts only).
- Provide lightweight schemas for `EntityRef`, `GeoURI`, `Observation`, and `TemporalKinds`.
- Enforce strict semantic definitions for temporal fields.
- Establish `geodomain.labels` as the single owner of class label taxonomies.
- Migrate `geomemory.core.models.Observation` to `geodomain.Observation`.

**Non-Goals:**
- No database tables, repositories, or SQLite in `geodomain`.
- No IO, network, ML, or raster processing in `geodomain`.
- No parallel `ObservationV2` — full migration of existing model.

## Decisions

### Decision 1: Dedicated Pure Domain Library (`libs/geodomain`)
- **Choice**: Create `libs/geodomain` with zero IO/DB/ML dependencies.
- **Rationale**: Enables `geomemory`, `geoagent`, `geolearn`, and `data_engine` to share canonical domain types without violating dependency rules or introducing circular imports.

### Decision 2: Canonical URI Scheme `geo:<type>/<id>`
- **Choice**: Standardize on `geo:<type>/<id>` (e.g. `geo:farm/<id>`, `geo:field/<id>`, `geo:scene/<id>`, `geo:observation/<id>`, `geo:asset/<sha256>`).
- **Rationale**: Structured namespace prevents collisions, is extensible across domains, and is easily parsed and serialized.

### Decision 3: Direct Migration of Existing `Observation`
- **Choice**: Migrate existing `Observation` in `geomemory` to `geodomain.Observation`.
- **Rationale**: Prevents permanent technical debt from having duplicate or parallel versions (`Observation` vs `ObservationV2`).

### Decision 4: Centralized Label Registry in `geodomain.labels`
- **Choice**: Put `LabelRegistry`, `LabelDefinition`, and `LabelSet` in `geodomain.labels`.
- **Rationale**: Both `geomemory` (feedback collection) and `geolearn` (classifier adaptation) need access to the same taxonomy without inter-dependency.

## Risks / Trade-offs

- [Risk] Updating existing `geomemory` code and tests for migrated `Observation`. → Mitigation: Maintain backward-compatible property aliases during transition and run full test suites.
