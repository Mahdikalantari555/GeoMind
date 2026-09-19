# run-storage Specification

## Purpose
Persists benchmark run artifacts to disk under `geomemory-evals/runs/` so runs
can be replayed and diffed across GeoMemory versions. Layout is
`runs/<dataset>/<timestamp>/` with a `stats.json` plus one per-benchmark result
file.

## Requirements

### Requirement: Run directory layout
Each run SHALL be written to `geomemory-evals/runs/<dataset>/<timestamp>/`
where `<timestamp>` is an ISO-8601 UTC timestamp with second precision.

#### Scenario: Run directory created
- **WHEN** a benchmark run completes for dataset `geospatial`
- **THEN** a directory `runs/geospatial/<timestamp>/` exists on disk

#### Scenario: Timestamp uniqueness
- **WHEN** two runs complete within the same second
- **THEN** the second run writes to a distinct directory (suffix or retry)

### Requirement: Stats artifact
Each run directory SHALL contain a `stats.json` file matching the pipeline
statistics schema.

#### Scenario: Stats written
- **WHEN** a run completes
- **THEN** `stats.json` is present and parses as valid JSON with all eight
  statistics fields

### Requirement: Per-benchmark result file
Each benchmark executed in a run SHALL produce a single `<benchmark>.json` file
containing the benchmark name, config, aggregated metrics, and per-query rows.

#### Scenario: Benchmark artifact
- **WHEN** benchmark `phase1.jsonl` runs
- **THEN** `phase1.jsonl.json` is written with `name`, `config`, `metrics`, and `rows`

#### Scenario: Per-query row schema
Each row in `rows` SHALL contain: `query`, `retrieved` (list of hit ids),
`scores` (list of floats aligned with retrieved), `metadata`, and `response`
(the generated answer text, or null when no LLM is configured).

### Requirement: No benchmark-specific ingestion logic
Run storage SHALL reuse only the production ingestion, retrieval, and QA code
paths. No eval-specific ingestion or retrieval logic shall exist.

#### Scenario: Production path used
- **WHEN** a benchmark run executes
- **THEN** the code path is identical to `geomemory ingest` and `geomemory search`

### Requirement: Artifact immutability
Once written, run artifacts SHALL NOT be modified by subsequent runs.

#### Scenario: No overwrite
- **WHEN** a run directory already exists
- **THEN** a new run writes to a new directory rather than mutating the old one
