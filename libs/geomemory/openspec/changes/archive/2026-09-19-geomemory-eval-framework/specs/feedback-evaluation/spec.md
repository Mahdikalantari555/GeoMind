## Purpose

Delta: extends the eval tooling with pipeline statistics, rebuild validation,
run persistence, and run comparison, layered on top of the existing
retrieval/QA benchmark metrics.

## MODIFIED Requirements

### Requirement: Retrieval metrics
The eval package SHALL compute recall@k, precision@k, MRR@k, and nDCG@k over labeled benchmark items.

#### Scenario: Benchmark run
- **WHEN** `geomemory eval run BENCHMARK.jsonl` executes
- **THEN** aggregated retrieval metrics print/emit in json or markdown

### Requirement: QA metrics
The eval package SHALL measure abstention accuracy/rate, citation correctness, and a faithfulness proxy for QA benchmarks.

#### Scenario: QA aggregation
- **WHEN** benchmark items include expected abstentions/citations
- **THEN** corresponding metric groups aggregate and report alongside retrieval metrics

## ADDED Requirements

### Requirement: Pipeline statistics command
The eval CLI SHALL expose `geomemory eval stats <dataset>` that ingests a dataset
into a scratch workspace and emits pipeline statistics.

#### Scenario: Stats command
- **WHEN** `geomemory eval stats datasets/geospatial` runs
- **THEN** statistics for files, documents, chunks, embeddings, entities,
  relations, duration, and storage size are printed and persisted to `stats.json`

### Requirement: Rebuild validation command
The eval CLI SHALL expose `geomemory eval rebuild <dataset>` that deletes and
recreates a scratch workspace, re-ingests the dataset through the production
pipeline, and emits statistics. It stops at statistics and does not rerun
benchmark queries.

#### Scenario: Rebuild succeeds
- **WHEN** `geomemory eval rebuild datasets/geospatial` runs on a clean machine
- **THEN** ingestion completes without errors and statistics are emitted

#### Scenario: Rebuild never touches real workspace
- **WHEN** `geomemory eval rebuild` runs
- **THEN** all writes target `geomemory-evals/workspaces/<dataset>/`, never the
  user's configured workspace

#### Scenario: Rebuild detects schema issues
- **WHEN** a schema migration is broken
- **THEN** rebuild fails loudly during re-ingestion rather than silently producing wrong stats

### Requirement: Comparison command
The eval CLI SHALL expose `geomemory eval compare <run_a> <run_b>` that diffs
two persisted runs and exits non-zero on any detected difference.

#### Scenario: Compare detects regression
- **WHEN** `geomemory eval compare runs/a runs/b` runs and runs differ
- **THEN** statistics and retrieval deltas are reported and the process exits non-zero

### Requirement: Per-query run artifacts
Benchmark runs SHALL persist per-query rows alongside aggregated metrics.

#### Scenario: Per-query artifact
- **WHEN** a benchmark run completes
- **THEN** a single `<benchmark>.json` file contains `name`, `config`, `metrics`,
  and `rows` with per-query retrieved ids, scores, metadata, and response