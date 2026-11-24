# regression-tracking Specification

## Purpose
Enables regression detection by allowing users to pin a named baseline run per dataset and compare subsequent runs against it. Drift is reported as per-metric deltas with optional threshold-based pass/fail semantics.

## Requirements

### Requirement: Baseline set
Users SHALL be able to pin the most recent run for a dataset as the active baseline via `geomemory eval baseline set <dataset>`.

#### Scenario: Set baseline
- **WHEN** `geomemory eval baseline set geospatial` runs and at least one run exists for `geospatial`
- **THEN** the newest run timestamp is recorded as the baseline in `geomemory-evals/baselines/<dataset>.json`

#### Scenario: No runs exist
- **WHEN** `geomemory eval baseline set geospatial` runs but no runs exist
- **THEN** the command exits non-zero with an error naming the absence of runs

### Requirement: Baseline get
Users SHALL be able to inspect the currently pinned baseline for a dataset via `geomemory eval baseline get <dataset>`.

#### Scenario: Baseline exists
- **WHEN** `geomemory eval baseline get geospatial` runs
- **THEN** the timestamp, path, and metrics of the baseline run are printed

#### Scenario: No baseline pinned
- **WHEN** `geomemory eval baseline get geospatial` runs with no pinned baseline
- **THEN** the command prints `No baseline set for dataset: geospatial` and exits zero

### Requirement: Baseline list
Users SHALL be able to list all datasets that have pinned baselines via `geomemory eval baseline list`.

#### Scenario: List baselines
- **WHEN** `geomemory eval baseline list` runs
- **THEN** each dataset with a baseline is printed alongside its pinned timestamp

### Requirement: Auto-compare on run
When `geomemory eval run` is invoked with `--baseline` on a dataset that has a pinned baseline, the run SHALL automatically compare itself against the baseline after completion.

#### Scenario: Run with auto-compare
- **WHEN** `geomemory eval run --baseline geospatial <benchmark>` runs
- **THEN** the runner detects the pinned baseline, computes the diff, and appends it to the stdout output

#### Scenario: No baseline pinned
- **WHEN** `geomemory eval run --baseline geospatial <benchmark>` runs but no baseline exists
- **THEN** the command exits non-zero naming the missing baseline

### Requirement: Drift detection
Comparison between a run and its baseline SHALL compute per-metric absolute and relative deltas. A configurable numeric threshold (`--threshold`, default `0.05` i.e. 5 %) SHALL mark a metric as "regressed" when the absolute change exceeds it in either direction.

#### Scenario: Metric within threshold
- **WHEN** recall@5 changes from 0.720 to 0.735 (delta 0.015) with default threshold
- **THEN** the metric is reported as unchanged (green / no-drift)

#### Scenario: Metric exceeds threshold
- **WHEN** precision@5 changes from 0.600 to 0.540 (delta −0.060) with default threshold
- **THEN** the metric is flagged as REGRESSED and highlighted in the diff output

#### Scenario: Custom threshold
- **WHEN** `--threshold 0.01` is passed and recall@5 changes by 0.008
- **THEN** the metric is flagged as REGRESSED because 0.008 > 0.01 is false — wait, 0.008 < 0.01, so it is NOT flagged

### Requirement: Regressions cause non-zero exit
When any metric is flagged as regressed during an auto-compare, the `geomemory eval run --baseline` process SHALL exit non-zero.

#### Scenario: Any regression detected
- **WHEN** `geomemory eval run --baseline geospatial phase1.jsonl` runs and one metric drifts beyond threshold
- **THEN** the process exits with code 1

#### Scenario: All metrics stable
- **WHEN** `geomemory eval run --baseline geospatial phase1.jsonl` runs and all metrics are within threshold
- **THEN** the process exits with code 0

### Requirement: Regression report structure
The regression diff SHALL be a structured object containing: `baseline_timestamp`, `current_timestamp`, `dataset`, `benchmarks` (list of per-benchmark diffs), and `summary` (counts of passed, regressed, improved metrics).

#### Scenario: Report contents
- **WHEN** comparison completes
- **THEN** the JSON report includes all four top-level keys with correctly populated values

### Requirement: Published baseline regression hook
The project SHALL publish a repeatable report at `docs/benchmarks/report.md`
with a frozen protocol, a retrieval-parity ablation (nDCG@10/MRR@10),
abstention precision/recall and a machine-checked citation-correctness
invariant. A CI job SHALL re-run the protocol and fail when a published
retrieval metric moves beyond the frozen tolerance or citation resolution
drops below 1.0. The README SHALL carry a summary results table.

#### Scenario: Published numbers cannot rot
- **WHEN** a change alters retrieval quality beyond ±0.02 on any published mode or breaks citation resolution
- **THEN** the benchmark CI job fails and the report must be regenerated in the same change

#### Scenario: Citation invariant
- **WHEN** the baseline pytest runs
- **THEN** every citation emitted by the deterministic QA stub resolves to an existing segment with a non-empty locator, otherwise the test fails
