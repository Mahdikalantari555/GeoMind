# ci-ready-output Specification

## Purpose
Ensures benchmark output is machine-parseable and CI-compatible so automated pipelines can detect regressions without human intervention. Structured JSON reports with strict exit codes replace ad-hoc Markdown summaries for programmatic consumption.

## Requirements

### Requirement: CI output flag
`geomemory eval compare` SHALL accept a `--ci` flag that produces a compact, machine-readable JSON report to stdout and suppresses the human-readable Markdown summary.

#### Scenario: CI mode enabled
- **WHEN** `geomemory eval compare --ci run_a run_b` runs
- **THEN** stdout contains only a single JSON object and no Markdown tables

#### Scenario: CI mode disabled (default)
- **WHEN** `geomemory eval compare run_a run_b` runs without `--ci`
- **THEN** the existing human-readable Markdown summary is emitted as before

### Requirement: Compact JSON schema
The CI-format JSON diff SHALL contain these top-level keys: `baseline_run`, `current_run`, `dataset`, `benchmarks` (array of per-benchmark diff objects), and `ok` (boolean — true when no regressions detected).

#### Scenario: Schema compliance
- **WHEN** a comparison completes in CI mode
- **THEN** every required top-level key is present in the JSON output

### Requirement: Per-benchmark diff fields
Each entry in the `benchmarks` array SHALL include: `name`, `metrics` (object mapping metric key → `{baseline, current, delta, regressed}`), and `queries` (list of per-query difference objects with `query`, `delta_retrieved_add`, `delta_retrieved_remove`).

#### Scenario: Metric diff shape
- **WHEN** a benchmark has a recall@5 change from 0.70 to 0.65
- **THEN** the metrics entry contains `{recall@5: {baseline: 0.70, current: 0.65, delta: -0.05, regressed: true}}`

### Requirement: Exit-on-regression for CI
In `--ci` mode, `geomemory eval compare` SHALL exit non-zero when any metric is flagged as regressed OR any retrieval diff contains missing results.

#### Scenario: Regression present
- **WHEN** comparison finds a metric drift beyond the implicit default threshold
- **THEN** exit code is 1

#### Scenario: No regression
- **WHEN** all metrics and retrieval results are identical between runs
- **THEN** exit code is 0

### Requirement: Threshold propagation
The `--threshold` flag accepted by `geomemory eval compare` SHALL apply equally in CI and non-CI modes.

#### Scenario: Custom threshold in CI
- **WHEN** `geomemory eval compare --ci --threshold 0.02 run_a run_b` runs
- **THEN** only metrics with absolute delta ≥ 0.02 are flagged as regressed in the JSON output

### Requirement: Silent comparison for empty deltas
When two runs are identical in every metric and retrieval result, the CI-mode JSON SHALL set `ok: true` and omit any non-zero delta entries from the `benchmarks[].metrics` object (present only keys with non-zero delta).

#### Scenario: Identical runs
- **WHEN** `geomemory eval compare --ci run_a run_a` runs
- **THEN** `ok` is `true` and each benchmark's `metrics` object is empty `{}`
