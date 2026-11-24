# studio-resources

## Purpose

Define the Resources page: how documents and spatial data enter the
workspace, how ingest progress is shown, and how collections and index state
are presented — without raw JSON and without blocking the UI.

## ADDED Requirements

### Requirement: Drag-drop ingest
The page SHALL accept file drops (PDF, TXT/MD, GeoTIFF, GeoJSON) and start
ingest jobs per file. Batch drops SHALL queue as separate jobs, each with
live progress (stage/percent/detail from `job.progress` SSE).

#### Scenario: Drop a batch
- **WHEN** the user drops 5 files
- **THEN** 5 ingest jobs queue and each shows independent live progress

#### Scenario: Unsupported file
- **WHEN** a file of unsupported type is dropped
- **THEN** it is rejected up front with the reason, and no job is created

### Requirement: Collections and index stats
The page SHALL list collections with asset counts and SHALL present index
status (segments, embeddings, model) as human-readable cards — raw JSON
dumps are forbidden.

#### Scenario: View index state
- **WHEN** the user opens Resources
- **THEN** collection cards and index stats render as formatted summaries

### Requirement: Ingest failure recovery
A failed ingest SHALL show the error reason and a retry action. Partial
results from a failed batch SHALL be visible (which files succeeded).

#### Scenario: One file fails in a batch
- **WHEN** one ingest job fails in a five-file batch
- **THEN** the other four complete visibly and the failed one offers retry
  with its error reason
