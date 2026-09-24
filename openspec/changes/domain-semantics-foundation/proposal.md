## Why

Domain concepts across GeoFoundation currently lack a unified semantic backbone:
1. **No Shared Identity Model**: Farms, parcels, satellite scenes, and observations are referenced as arbitrary strings or file paths with no universal identifier or linkage between GeoMemory knowledge, Data Engine rasters, and GeoAgent tools.
2. **Temporal Ambiguity**: Five timestamp concepts (`acquired_at`, `observed_at`, `published_at`, `ingested_at`, `created_at`) are used inconsistently across libraries without strict semantics or timezone discipline.
3. **Unowned Label Strings**: Ground-truth labels, feedback categories, and stress classes float as unstructured integers or arbitrary strings across JSON blobs without validation or versioning.

A shared domain semantics foundation is required to establish consistent identity, event observation, temporal modeling, and label taxonomy across all four libraries.

## What Changes

- **Canonical Identity Model & EntityRef**:
  - Introduce `EntityRef` (type, id, uri) supporting canonical schemes: `farm:<id>`, `field:<id>`, `scene:<id>`, `observation:<id>`, `asset:<sha256>`.
  - Establish entity linkage enabling any model prediction, candidate memory, or tool output to reference its underlying real-world entity unambiguously.
- **Unified Observation Model**:
  - Define the `Observation` domain contract representing a measured or inferred agricultural/remote-sensing fact, binding spatial coordinates, observed property, timestamp, sensor source, and confidence.
- **Strict Temporal Model**:
  - Formally delineate and validate timestamp fields:
    * `acquired_at`: Exact sensor/satellite image capture UTC time.
    * `observed_at`: Agronomic occurrence time in the physical field.
    * `published_at`: Document or research source release date.
    * `ingested_at`: Storage and SHA-256 ingestion timestamp in GeoMemory.
    * `created_at`: System operational execution or record creation timestamp.
- **Authoritative Label Taxonomy (`geolearn.labels`)**:
  - Establish `geolearn.labels` housing `LabelDefinition`, `LabelSet`, and `LabelRegistry`.
  - Provide versioned, typed taxonomies for stress differentiation (e.g. `water_stress`, `nitrogen_deficiency`, `salinity_stress`, `healthy_canopy`) shared across feedback collection and classifier training.

## Capabilities

### New Capabilities
- `domain-semantics`: Universal entity identity, observation schema, temporal semantics, and label taxonomy.

## Impact

- `libs/geolearn`: Introduces `geolearn.labels` as the authoritative label taxonomy registry.
- `libs/geomemory`: Adopts `EntityRef` and strict temporal validation across `Segment`, `CandidateMemory`, and `Asset`.
- `libs/geoagent`: References canonical `EntityRef` in GIS and advisor tools.
- `libs/data_engine`: Emits `Observation` and `acquired_at` standard metadata from scene readers.
