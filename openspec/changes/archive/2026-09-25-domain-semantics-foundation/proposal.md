## Why

Domain concepts across GeoFoundation currently lack a unified semantic backbone:
1. **No Shared Identity Model**: Farms, parcels, satellite scenes, and observations are referenced as arbitrary strings or file paths with no universal identifier or linkage between GeoMemory knowledge, Data Engine rasters, and GeoAgent tools.
2. **Temporal Ambiguity**: Five timestamp concepts (`acquired_at`, `observed_at`, `published_at`, `ingested_at`, `created_at`) are used inconsistently across libraries without strict semantics or timezone discipline.
3. **Unowned Label Strings**: Ground-truth labels, feedback categories, and stress classes float as unstructured integers or arbitrary strings across JSON blobs without validation or versioning.
4. **Observation Fragmentation**: `Observation` models risk divergent implementations across libraries without a single pure-domain definition.

A dedicated shared domain library (`libs/geodomain`) is required to establish consistent identity, event observation, temporal modeling, and label taxonomy across all libraries without violating the dependency graph.

## What Changes

- **New Pure Domain Library (`libs/geodomain`)**:
  - Establish `libs/geodomain` containing pure domain models and contracts (Pydantic v2):
    * Zero SQLite, zero repositories, zero services.
    * Zero IO, zero ML, zero raster dependencies.
    * Independent dependency target for `geomemory`, `geoagent`, `geolearn`, and `data_engine`.
- **Canonical Identity Model & GeoURI**:
  - Introduce `EntityRef` (type, id) with canonical URI scheme `geo:<type>/<id>`:
    * `geo:farm/<id>`
    * `geo:field/<id>`
    * `geo:scene/<id>`
    * `geo:observation/<id>`
    * `geo:asset/<sha256>`
  - Establish entity linkage enabling any model prediction, candidate memory, or tool output to reference its underlying real-world entity unambiguously.
- **Unified Observation Model & Migration**:
  - Define authoritative `Observation`, `ObservationRef`, and `ObservationKind` in `geodomain`.
  - Migrate `geomemory.core.models.Observation` directly to `geodomain.Observation` (avoiding parallel duplicate models or debt).
- **Strict Temporal Model**:
  - Formally delineate and validate timestamp fields as ISO-8601 UTC:
    * `acquired_at`: Exact sensor/satellite image capture UTC time.
    * `observed_at`: Agronomic occurrence time in the physical field.
    * `published_at`: Document or research source release date.
    * `ingested_at`: Storage and SHA-256 ingestion timestamp in GeoMemory.
    * `created_at`: System operational execution or record creation timestamp.
- **Authoritative Label Taxonomy (`geodomain.labels`)**:
  - Establish `geodomain.labels` housing `LabelDefinition`, `LabelSet`, and `LabelRegistry`.
  - Provide versioned, typed taxonomies for stress differentiation (e.g. `water_stress`, `nitrogen_deficiency`, `salinity_stress`, `healthy_canopy`) shared across feedback collection and classifier training.

## Capabilities

### New Capabilities
- `domain-semantics`: Universal entity identity, observation schema, temporal semantics, and label taxonomy via `geodomain`.

## Impact

- `libs/geodomain`: New library package hosting pure domain types and contracts.
- `libs/geomemory`: Migrates legacy `Observation` to `geodomain.Observation`; adopts `EntityRef` and strict temporal validation across `Segment`, `CandidateMemory`, and `Asset`.
- `libs/geoagent`: References canonical `EntityRef` in GIS and advisor tools.
- `libs/data_engine`: Emits `Observation` and `acquired_at` standard metadata from scene readers.
- `libs/geolearn`: References `geodomain.labels.LabelRegistry` for stress classes and training labels.
