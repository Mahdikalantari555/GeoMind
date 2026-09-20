# Storage & Persistence — As-Is Specification

Baseline extracted from current implementation. Describes existing behavior only.

## Purpose

GeoMemory persists workspace state, migrations, indexes, and content-addressed artifacts in a durable local store while preserving data integrity and traceability.

## Requirements

### Requirement: Single-file database
All structured state SHALL live in one SQLite database per workspace, opened in WAL mode with foreign keys enforced.

#### Scenario: Connect
- **WHEN** `connect(db_path)` runs
- **THEN** WAL and `foreign_keys=ON` are active and schema is ensured

### Requirement: Versioned migrations
Schema changes SHALL be applied through a version registry (`schema_migration` table) with idempotent application. The candidate-memory migration SHALL add nullable `observed_at`, `superseded_by`, and `project` columns, widen the allowed `memory_type` values, and preserve existing candidate rows and provenance foreign keys.

#### Scenario: Fresh database
- **WHEN** initialization runs on an empty database
- **THEN** schema version 1 is created and subsequent migrations are recorded idempotently

#### Scenario: Candidate temporal migration
- **WHEN** a database containing candidate memories and provenance rows is migrated
- **THEN** existing rows remain readable, the three temporal/entity columns are present, and the self-referencing supersession foreign key is enforced

### Requirement: Sparse index integrity
FTS5 (`segments_fts`) SHALL mirror the `segment` table via triggers so text search never diverges from stored segments.

#### Scenario: Insert segment
- **WHEN** a segment row is inserted/updated/deleted
- **THEN** the FTS index reflects it without manual sync

### Requirement: Spatial index
Spatial bboxes SHALL be queryable through an RTree virtual table keyed by a mapping table that preserves TEXT entity ids.

#### Scenario: Bbox lookup
- **WHEN** spatial entities are persisted and queried by bbox
- **THEN** matching entity ids return via the RTree + mapping join

### Requirement: Content-addressed object store
Raw bytes SHALL be stored once under their SHA-256 hash at `objects/<aa>/<bb>/<hash>`, immutable; the store exposes put/get/exists/delete/size and total counts.

#### Scenario: Put bytes
- **WHEN** bytes are stored
- **THEN** returned hash equals content SHA-256 and re-storing is a no-op dedupe

### Requirement: Typed repositories
Domain tables SHALL be accessed through typed repositories with parameterized SQL (no string interpolation).

#### Scenario: Repository round-trip
- **WHEN** models are written and read back through repositories
- **THEN** field fidelity holds (ids, JSON metadata, timestamps)

### Requirement: Temporal candidate storage
The persistence layer SHALL support reading candidates by project and memory type with stable descending observation ordering and offset/limit pagination.

#### Scenario: Project listing
- **WHEN** candidates are listed for a project with a memory-type filter
- **THEN** only matching rows are returned in newest-observed-first order
