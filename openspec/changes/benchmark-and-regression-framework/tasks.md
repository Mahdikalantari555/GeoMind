## 1. Corpus Registry

- [ ] 1.1 Create `geomemory-evals/corpus/corpus.json` schema and write a loader function `load_corpus_registry(path)` in `libs/geomemory/src/geomemory/eval/corpus.py`; verify with a unit test that parses a valid registry and rejects a missing file
- [ ] 1.2 Add `geomemory eval corpus list` CLI command that enumerates all `.jsonl` files under `geomemory-evals/corpus/*/` grouped by version; verify by running the command against the empty corpus dir and observing an empty listing
- [ ] 1.3 Implement version resolution: when `load_benchmark()` reads a `.jsonl`, look up its entry in `corpus.json` and attach `"corpus_version"` to the resulting `Benchmark.metadata`; verify with a test that loads a benchmark and asserts the version field

## 2. Benchmark Item Schema Validation

- [ ] 2.1 Add a `validate_benchmark_items(rows)` helper in `corpus.py` that re-runs `BenchmarkItem` validation on raw dicts and returns a structured error list; verify with pytest cases for valid items, empty query, and missing gold_ids type
- [ ] 2.2 Extend `load_benchmark()` to call the validator before constructing the `Benchmark` object, raising `ValueError` with line-number context on the first invalid row; verify with a malformed JSONL fixture file

## 3. Baseline Management CLI

- [ ] 3.1 Create `geomemory-evals/baselines/` directory structure and a `BaselineStore` class in `run_store.py` (or a new `baselines.py`) with `set(dataset, timestamp, path)`, `get(dataset)`, and `list_datasets()` methods; verify with unit tests covering set/get/list and missing-baseline case
- [ ] 3.2 Add `geomemory eval baseline set <dataset>`, `geomemory eval baseline get <dataset>`, and `geomemory eval baseline list` CLI subcommands; verify each subcommand produces the expected output against a fake `RunStore`
- [ ] 3.3 Handle the case where no runs exist for a dataset in `baseline set` — exit non-zero with a clear message; verify with a test using an empty run store

## 4. Regression Detection Logic

- [ ] 4.1 Implement `detect_drift(baseline_metrics, current_metrics, threshold=0.05)` in `libs/geomemory/src/geomemory/eval/regression.py` that computes absolute deltas and returns a dict mapping metric name → `{baseline, current, delta, regressed}`; verify with unit tests covering within-threshold, exceeded-threshold, and exact-equality cases
- [ ] 4.2 Add `--threshold` flag to `geomemory eval compare` that passes through to the drift detection function; verify the flag overrides the default and the correct metrics are flagged
- [ ] 4.3 Integrate drift detection into `eval run --baseline <dataset>`: after writing the run, resolve the baseline via `BaselineStore.get()`, load both runs, compute the diff, append the regression report to stdout, and exit non-zero on any regression; verify end-to-end with two synthetic runs

## 5. CI-Ready Output

- [ ] 5.1 Add a `to_ci_json(diff_result)` serializer in `regression.py` that emits the compact JSON structure described in the spec (`baseline_run`, `current_run`, `dataset`, `benchmarks`, `ok`); verify round-trip serialization preserves all fields
- [ ] 5.2 Add `--ci` flag to `geomemory eval compare` that routes output through `to_ci_json()` instead of `markdown_report()`; verify the flag suppresses Markdown and produces valid JSON on stdout
- [ ] 5.3 Ensure `--ci` mode exits non-zero when `ok` is false (any regression detected) and exits zero when `ok` is true; verify with two synthetic runs that differ in exactly one metric

## 6. Integration and Regression Tests

- [ ] 6.1 Write an integration test that creates a temporary corpus, runs two benchmarks with deliberately drifted metrics, pins a baseline, runs again with `--baseline`, and asserts the process exits non-zero and the CI JSON contains the expected regression flags
- [ ] 6.2 Write an integration test verifying that identical runs with `--baseline` exit zero and produce `ok: true` in CI mode
- [ ] 6.3 Run the full geomemory eval test suite (`pytest libs/geomemory/tests/eval/ -q`) and confirm zero regressions in existing tests

## 7. Documentation

- [ ] 7.1 Add a short README section or docstring block to `geomemory/eval/corpus.py` describing the corpus directory layout and how to add a new benchmark; verify the docs render correctly in the geomemory doc build
- [ ] 7.2 Update the geomemory CLI help text for `eval run`, `eval compare`, and the new `eval baseline` / `eval corpus` subcommands so flags and descriptions match the implemented behavior; verify by running `geomemory eval --help` and checking output
