## Context

GeoMemory already has a working eval subsystem (`libs/geomemory/src/geomemory/eval/`) with `runner.py`, `reporter.py`, `retrieval_metrics.py`, `qa_metrics.py`, `run_store.py`, and `benchmark.py`. Existing OpenSpec capabilities (`eval-datasets`, `run-storage`, `run-comparison`, `pipeline-stats`, `feedback-evaluation`) cover dataset layout, run persistence, two-run comparison, stats collection, and the as-is baseline. What is missing is a **fixed regression corpus** (versioned JSONL files with gold labels), **baseline pinning**, **automated drift detection**, and **CI-friendly structured output**. The new code must integrate cleanly with the existing `RunStore` layout and the production `search` / `ask` pipelines without introducing eval-specific ingestion logic.

## Goals / Non-Goals

**Goals:**
- Define and document a versioned corpus directory structure with a registry manifest.
- Add CLI commands for baseline management (`set`, `get`, `list`) and auto-compare on `eval run`.
- Extend `RunStore` with a baseline-resolution path (read `baselines/<dataset>.json` to locate the reference run).
- Implement drift detection with configurable per-metric thresholds.
- Add `--ci` flag to `eval compare` that emits compact JSON and enforces exit-on-regression semantics.

**Non-Goals:**
- Adding new retrieval or QA metric functions (the existing metrics are sufficient).
- Changing the `BenchmarkItem` schema or the JSONL loading path.
- Building a web dashboard for benchmark visualization (out of scope for this change).
- Migrating existing in-repo datasets to the new corpus format (handled separately if needed).
- Cross-lib changes beyond geomemory's eval package.

## Decisions

### D1: Corpus lives at `geomemory-evals/corpus/<version>/<name>.jsonl`

**Choice**: Versioned directories under `geomemory-evals/corpus/`, not under `datasets/`.
**Rationale**: The `datasets/` directory is already used by `eval-datasets` for ingestible source material. Benchmarks are *queries against* an ingested dataset, not sources themselves. Separating them avoids confusion between source data and evaluation questions.
**Alternatives considered**: Flat `corpus.jsonl` files; embedding version in filename. Rejected because flat files make version history hard to audit and filenames are fragile for semver tracking.

### D2: Baseline storage as a JSON file per dataset

**Choice**: `geomemory-evals/baselines/<dataset>.json` containing `{timestamp, path}`.
**Rationale**: Simple key-value lookup, no schema migration, aligns with the existing `RunStore` pattern. A SQLite table would add unnecessary complexity for a single value per dataset.
**Alternatives considered**: Embedding baseline timestamp in `corpus.json`; storing in the workspace DB. Rejected because baselines are eval-side concerns, not workspace concerns.

### D3: Drift detection as an extension of `run-comparison`, not a separate command

**Choice**: `eval run --baseline <dataset>` performs an implicit `compare` after writing the run. The existing `eval compare` command gains a `--threshold` flag for consistency.
**Rationale**: Avoids command duplication. The comparison logic in `run_comparison.py` (or its equivalent) is already shared — we extend it rather than fork it.
**Alternatives considered**: New `eval regress` command. Rejected because it would duplicate the compare implementation and the natural user workflow is "run and check".

### D4: `--ci` flag on `eval compare` produces JSON but keeps the same exit-code semantics as before

**Choice**: `--ci` switches output format only; exit-on-regression is controlled independently by `--threshold`.
**Rationale**: Existing users of `eval compare` rely on exit code 1 when runs differ (any difference). The `--ci` flag should not change this contract — it only changes the output shape. CI pipelines can parse the JSON regardless.
**Alternatives considered**: `--ci` implies `--threshold 0`. Rejected because it would be a breaking change for existing workflows.

### D5: No new external dependencies

**Choice**: All functionality uses existing stdlib (`json`, `pathlib`, `datetime`) plus PyYAML which is already a declared dependency.
**Rationale**: Keeps the eval package lightweight and consistent with geomemory's zero-new-dep policy.
**Alternatives considered**: Using a diff library (e.g., `deepdiff`). Rejected because the delta computation is simple enough to implement inline.

## Risks / Trade-offs

- **[Risk] Corpus version drift**: Users may update benchmark `.jsonl` files without bumping the version tag, silently changing the ground truth.
  → **Mitigation**: Require a semver bump in `corpus.json` when any item is added, removed, or modified; emit a warning on version mismatch between corpus file mtime and registry version.

- **[Risk] Baseline staleness**: A pinned baseline from months ago may become an irrelevant reference point.
  → **Mitigation**: `baseline get` prints the age of the pinned baseline; add a future `baseline expire` sub-command (deferred, not in this change).

- **[Risk] Threshold rigidity**: A single global `--threshold` applies to all metrics uniformly, which may be too strict for noisy metrics (e.g., faithfulness_proxy) and too loose for stable ones (e.g., precision@5).
  → **Mitigation**: Document the default threshold and its rationale; accept per-metric thresholds via a future config file (deferred).

- **[Trade-off] JSONL-only corpus format**: Restricting to JSONL simplifies the loader but excludes users who prefer YAML or CSV benchmarks.
  → **Mitigation**: The `load_benchmark()` function already accepts any valid BenchmarkItem JSONL; adding YAML support can be a follow-up change without breaking this one.

## Migration Plan

No migration is required for existing installations. The new corpus directory is optional — existing `geomemory eval run <path>.jsonl` behavior is unchanged. To adopt the new framework:

1. Create `geomemory-evals/corpus/v0.1.0/` and populate with initial benchmark JSONL files.
2. Write `geomemory-evals/corpus/corpus.json` describing each benchmark.
3. Run `geomemory eval rebuild` on each dataset to create an initial run.
4. Pin the run as baseline: `geomemory eval baseline set <dataset>`.
5. Future runs with `--baseline <dataset>` will automatically detect regressions.

Rollback: Removing `geomemory-evals/corpus/` and `geomemory-evals/baselines/` restores the prior state; no database schema changes are involved.

## Open Questions

- Should `geomemory eval run --baseline` automatically update the baseline when the run *improves* significantly (not just on any change)? Currently the spec says no — baseline is pinned manually. This is deferrable.
- Should the `corpus.json` registry be authored by humans or generated from the corpus directory? Manual authorship gives more control over descriptions but is error-prone; auto-generation risks missing context. Decision deferred to implementation.
- Is a 5 % default threshold appropriate for all metric families, or should retrieval and QA metrics use different defaults? Deferred — the uniform threshold satisfies the first iteration.
