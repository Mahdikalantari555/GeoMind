## Context

Currently, entity IDs, timestamps, and classification labels are defined ad-hoc across libraries as unstructured strings. This causes ownership drift where the same farm or observation cannot be traced across GeoMemory, GeoAgent, and GeoLearn.

## Goals / Non-Goals

**Goals:**
- Provide lightweight Pydantic schemas for `EntityRef` and `Observation`.
- Enforce strict semantic definitions for temporal fields.
- Establish `geolearn.labels` as the single owner of class label taxonomies.

**Non-Goals:**
- Heavy distributed identity infrastructure (no centralized identity server; identities are deterministic URI strings).
- Enforcing database foreign keys across SQLite files.

## Decisions

### Decision 1: URI-based EntityRef
- **Choice**: `EntityRef(type: str, id: str)` with string representation `geo:<type>/<id>`.
- **Rationale**: Portable across JSON serialization, database columns, and URL paths without requiring database joins.

### Decision 2: Centralized Label Registry in GeoLearn
- **Choice**: Put `LabelRegistry` in `geolearn.labels`.
- **Rationale**: GeoLearn is the statistical learning layer that actually consumes and trains against these labels.

## Risks / Trade-offs

- [Risk] Legacy candidate memories have unvalidated label strings. → Mitigation: Provide default migration fallbacks in `LabelRegistry.resolve()`.
