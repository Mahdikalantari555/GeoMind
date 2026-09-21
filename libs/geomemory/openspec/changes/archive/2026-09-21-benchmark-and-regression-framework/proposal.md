## Why

GeoMemory's eval subsystem already runs benchmarks and persists runs, but there is no fixed regression corpus — no stable set of JSONL benchmark files that can serve as a ground-truth baseline across GeoMemory versions. Without one, regressions in retrieval quality or QA correctness go undetected between releases, and every benchmark run must be hand-built from scratch. A versioned, in-repo corpus plus baseline tracking and CI-friendly diff output will make benchmark drift visible the moment it occurs.

## What Changes

- Add a versioned benchmark corpus under `geomemory-evals/corpus/` containing fixed JSONL benchmark files with gold-label annotations for retrieval and QA evaluation.
- Introduce a benchmark registry schema (`corpus.json`) that declares each benchmark's version, description, modality, and intended use.
- Extend run storage to support baseline comparisons: a named "baseline" tag that pins a reference run, and automatic comparison on subsequent runs against that baseline.
- Add a regression detection mode to `geomemory eval run` that compares the current run against the latest baseline and exits non-zero on statistically significant metric drift (configurable threshold).
- Emit structured machine-readable output (JSON diff report) from `geomemory eval compare` suitable for CI consumption, with a `--ci` flag that sets strict exit codes.
- Add a `geomemory eval baseline set|get|list` CLI surface for managing pinned baselines per dataset.

## Capabilities

### New Capabilities

- `benchmark-corpus`: Fixed, versioned JSONL benchmark datasets with a registry manifest (`corpus.json`) providing dataset descriptions, modalities, version tags, and gold-label annotations.
- `regression-tracking`: Pinning a baseline run per dataset and automatically detecting metric drift on subsequent evaluations against that baseline, with configurable thresholds.
- `ci-ready-output`: Machine-parseable JSON diff reports from run comparison, with a `--ci` flag that enforces strict exit-on-regression behavior.

### Modified Capabilities

<!-- None — existing geomemory specs (eval-datasets, run-storage, run-comparison, pipeline-stats) describe existing behavior; this change adds new concerns without altering their requirements. -->

## Impact

- **Code**: New modules in `libs/geomemory/src/geomemory/eval/corpus.py` (registry loader), `libs/geomemory/src/geomemory/eval/regression.py` (drift detection), additions to `run_store.py` for baseline tagging.
- **CLI**: New commands under `geomemory eval corpus`, `geomemory eval baseline`, extended flags on `geomemory eval run` (`--baseline`, `--ci`, `--threshold`).
- **Data layout**: New `geomemory-evals/corpus/<version>/<benchmark>.jsonl` directories; `geomemory-evals/corpus/corpus.json` registry file.
- **Dependencies**: No new external dependencies. Uses existing PyYAML / JSON infrastructure already declared in geomemory.
- **Tests**: New pytest cases in `libs/geomemory/tests/eval/test_corpus.py`, `test_regression.py`; existing `test_run_storage.py` and `test_run_comparison.py` remain unchanged.
