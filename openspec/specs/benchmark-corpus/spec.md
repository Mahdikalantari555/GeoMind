# benchmark-corpus Specification

## Purpose
Provides a fixed, versioned corpus of JSONL benchmark files with gold-label annotations that serve as the authoritative evaluation ground truth for GeoMemory retrieval and QA pipelines. A registry manifest (`corpus.json`) describes each benchmark's version, modality, and intended scope so corpora are traceable and reproducible across releases.

## Requirements

### Requirement: Corpus directory layout
The benchmark corpus SHALL live under `geomemory-evals/corpus/<version>/` where `<version>` is a semver-like string (e.g., `v0.1.0`). Each benchmark is a `.jsonl` file inside that version directory.

#### Scenario: Corpus discovery
- **WHEN** `geomemory eval corpus list` runs
- **THEN** all `.jsonl` files under `geomemory-evals/corpus/*/` are enumerated grouped by version

#### Scenario: Missing corpus directory
- **WHEN** no corpus directory exists yet
- **THEN** the command exits successfully and reports an empty corpus

### Requirement: Benchmark registry manifest
A top-level `geomemory-evals/corpus/corpus.json` SHALL exist as a JSON object mapping each benchmark name to metadata: `version`, `description`, `modality` (`retrieval`, `qa`, or `combined`), and `source_dataset` (the dataset it exercises).

#### Scenario: Valid registry
- **WHEN** `corpus.json` lists a benchmark with all required fields
- **THEN** the benchmark is recognized and available for evaluation

#### Scenario: Unknown benchmark referenced
- **WHEN** a `.jsonl` file exists but has no entry in `corpus.json`
- **THEN** the benchmark is still loadable but emits a warning noting the missing registry entry

### Requirement: JSONL benchmark item schema
Each line in a benchmark `.jsonl` file SHALL conform to the `BenchmarkItem` Pydantic model: `query` (required, non-empty), `gold_ids` (optional list of segment ids), `reference_answer` (optional string), `expected_abstain` (optional boolean, default false), and `metadata` (optional dict).

#### Scenario: Well-formed benchmark
- **WHEN** a `.jsonl` file contains valid BenchmarkItem lines
- **THEN** it loads successfully via `load_benchmark()`

#### Scenario: Invalid line
- **WHEN** a line fails Pydantic validation (e.g., empty query)
- **THEN** loading raises a descriptive error naming the line number and the failed field

### Requirement: Version pinning
Runs SHALL record the corpus version they were evaluated against. When a benchmark is loaded, its version SHALL be resolved from `corpus.json` and stored in the run's metadata.

#### Scenario: Version recorded
- **WHEN** a benchmark from `corpus/v0.1.0/phase1.jsonl` is run
- **THEN** the resulting run artifact records `"corpus_version": "v0.1.0"` in its metadata

#### Scenario: Version mismatch
- **WHEN** a previously run benchmark's corpus version is no longer present
- **THEN** the runner warns but still executes using the available file

### Requirement: Reproducible ordering
Benchmark items SHALL be processed in the exact order they appear in the `.jsonl` file. No shuffling or randomization is permitted.

#### Scenario: Deterministic order
- **WHEN** the same `.jsonl` file is run twice with identical config
- **THEN** per-query rows appear in the same order in both result artifacts
