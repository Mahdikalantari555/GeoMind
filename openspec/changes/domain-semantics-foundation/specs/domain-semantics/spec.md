## Purpose

Establishes the authoritative shared domain semantics across GeoFoundation, including universal entity identifiers (EntityRef), biophysical observation records, formal temporal semantics, and the label taxonomy registry.

## ADDED Requirements

### Requirement: Canonical Entity Identifiers
The system SHALL support typed canonical identifiers via `EntityRef(type, id)` formatted as deterministic URI schemes (e.g. `geo:farm/<id>`, `geo:field/<id>`, `geo:scene/<id>`, `geo:observation/<id>`).

#### Scenario: Cross-library entity resolution
- **WHEN** a GeoAgent tool produces a spatial output for a farm field
- **THEN** it attaches an `EntityRef(type="field", id="...")` allowing GeoMemory and GeoLearn to index and associate facts with the exact same entity

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
The `geolearn.labels` module SHALL define `LabelDefinition`, `LabelSet`, and `LabelRegistry`, providing versioned mappings between categorical names, class indices, and stress taxonomies.

#### Scenario: Validating feedback against label registry
- **WHEN** a user or agent submits a feedback label for a candidate memory
- **THEN** the label is validated against the active `LabelRegistry` for that crop and region
