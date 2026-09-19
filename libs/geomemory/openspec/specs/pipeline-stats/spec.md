# pipeline-stats Specification

## Purpose
Captures pipeline-level statistics after a full ingestion run: file counts,
document/chunk/embedding tallies, entity and relation counts, processing
duration, and storage footprint. Emits a stable `stats.json` schema so runs
across versions remain comparable.

## Requirements

### Requirement: Statistics collection after ingestion
The system SHALL collect statistics by querying the workspace after a complete
ingestion run, using only the production database tables.

#### Scenario: Stats after ingest
- **WHEN** a dataset is fully ingested into a workspace
- **THEN** `stats()` returns counts for files, documents, chunks, embeddings,
  entities, and relations, plus duration and storage size

### Requirement: Statistics schema
Statistics SHALL be emitted as a JSON object with these fields, all numeric:

| Field | Meaning |
|---|---|
| `files` | Number of source files processed |
| `documents` | Number of asset revisions created |
| `chunks` | Number of `segment` rows |
| `embeddings` | Number of `embedding_record` rows |
| `entities` | Number of `entity` rows |
| `relations` | Number of `relation` rows |
| `duration_seconds` | Wall-clock duration of the ingestion pipeline |
| `storage_bytes` | Total size of the workspace on disk |

#### Scenario: Schema completeness
- **WHEN** stats are emitted
- **THEN** all eight fields above are present in the output

#### Scenario: Numeric types
- **WHEN** stats are serialized to JSON
- **THEN** every field is a JSON number, never a string

### Requirement: Duration measurement
`duration_seconds` SHALL measure the wall-clock time of the ingestion phase only,
from the start of the first file read to the completion of the last job.

#### Scenario: Duration captured
- **WHEN** ingestion runs for 34.2 seconds
- **THEN** `duration_seconds` is approximately 34.2

### Requirement: Storage size
`storage_bytes` SHALL be the total on-disk size of the workspace directory,
including the database, object store, and index artifacts.

#### Scenario: Size captured
- **WHEN** a workspace occupies 1.2 GB on disk
- **THEN** `storage_bytes` reports approximately 1,200,000,000

### Requirement: Empty workspace
Statistics on a freshly created, un-ingested workspace SHALL report zero counts
and a non-negative duration.

#### Scenario: Fresh workspace
- **WHEN** stats are collected before any ingestion
- **THEN** `files`, `documents`, `chunks`, `embeddings`, `entities`, and `relations`
  are all `0`
