# domain-semantics Specification

## Purpose
Establishes the authoritative shared domain semantics across GeoFoundation via `geodomain`, including universal entity identifiers (`EntityRef`, `GeoURI`), biophysical observation records, formal temporal semantics, and the label taxonomy registry.

## Requirements

### Requirement: Canonical Entity Identifiers via GeoURI
The system SHALL support typed canonical identifiers via `EntityRef(type, id)` formatted with the deterministic URI scheme `geo:<type>/<id>` (e.g. `geo:farm/<id>`, `geo:field/<id>`, `geo:scene/<id>`, `geo:observation/<id>`, `geo:asset/<sha256>`).

#### Scenario: Cross-library entity resolution
- **WHEN** a GeoAgent tool produces a spatial output for a farm field
- **THEN** it attaches an `EntityRef(type="field", id="...")` allowing GeoMemory and GeoLearn to index and associate facts with the exact same entity

### Requirement: Pure Domain Library Structure
The `geodomain` package SHALL contain only pure Pydantic v2 data models and domain contracts without database, repository, service, IO, ML, or raster dependencies.

#### Scenario: Clean dependency import
- **WHEN** any library (`geomemory`, `geolearn`, `geoagent`, `data_engine`) imports `geodomain`
- **THEN** no heavy third-party dependencies or side effects are introduced

### Requirement: Migrated Observation Contract
The `geodomain.observation` module SHALL provide the authoritative `Observation` model, and `geomemory` SHALL migrate its existing observation model to this definition without creating parallel versions.

#### Scenario: Observation recording and retrieval
- **WHEN** an observation is recorded or queried across libraries
- **THEN** it conforms to `geodomain.Observation` specifying subject reference, metric, value, unit, timestamps, and confidence

### Requirement: Strict Temporal Field Discipline
The system SHALL strictly validate and distinguish all timestamp fields as ISO-8601 UTC strings according to their semantic role:
- `acquired_at`: Exact sensor/satellite image capture UTC time.
- `observed_at`: Real-world agronomic occurrence time.
- `published_at`: Formal publication or document release date.
- `ingested_at`: Storage and SHA-256 ingestion timestamp in GeoMemory.
- `created_at`: Computation or system record creation timestamp.

#### Scenario: Temporal validation on ingest
- **WHEN** an asset or segment carries multiple timestamps
- **THEN** each field is validated to represent its distinct semantic role without conflation

### Requirement: Authoritative Label Registry
The `geodomain.labels` module SHALL define `LabelDefinition`, `LabelSet`, and `LabelRegistry`, providing versioned mappings between categorical names, class indices, and stress taxonomies.

#### Scenario: Validating feedback against label registry
- **WHEN** a user or agent submits a feedback label for a candidate memory
- **THEN** the label is validated against the active `LabelRegistry` for that crop and region
