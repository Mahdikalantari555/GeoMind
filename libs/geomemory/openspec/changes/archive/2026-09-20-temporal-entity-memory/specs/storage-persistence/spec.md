## MODIFIED Requirements

### Requirement: Versioned migrations
Schema changes SHALL be applied through a version registry (`schema_migration` table) with idempotent application. The candidate-memory migration SHALL add nullable `observed_at`, `superseded_by`, and `project` columns, widen the allowed `memory_type` values, and preserve existing candidate rows and provenance foreign keys.

#### Scenario: Fresh database
- **WHEN** initialization runs on an empty database
- **THEN** schema version 1 is created and subsequent migrations are recorded idempotently

#### Scenario: Candidate temporal migration
- **WHEN** a database containing candidate memories and provenance rows is migrated
- **THEN** existing rows remain readable, the three temporal/entity columns are present, and the self-referencing supersession foreign key is enforced

## ADDED Requirements

### Requirement: Temporal candidate storage
The persistence layer SHALL support reading candidates by project and memory type with stable descending observation ordering and offset/limit pagination.

#### Scenario: Project listing
- **WHEN** candidates are listed for a project with a memory-type filter
- **THEN** only matching rows are returned in newest-observed-first order
