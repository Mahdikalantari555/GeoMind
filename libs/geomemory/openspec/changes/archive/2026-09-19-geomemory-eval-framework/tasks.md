## 1. Shapefile loader

- [x] 1.1 Create `src/geomemory/ingest/loaders/shapefile.py` with a `ShapefileLoader`
  implementing the `Loader` protocol, gated on the `rs` extra (geopandas/shapely)
  and raising a clear `RuntimeError` when absent. Verify: importing the module
  without `rs` raises a dependency-naming error.
- [x] 1.2 Register the loader in `default_loader_registry()` for shapefile media and
  add extension fallback for `.shp` in `get_loader()`. Verify: a `.shp` source
  resolves to `ShapefileLoader` through the default registry.
- [x] 1.3 Add a unit test covering ingest of a small shapefile (attributes + geometry
  into typed segments and a `vector_layer` row). Verify: `pytest geomemorytest`
  passes the new test.

## 2. Eval dataset tree and baseline

- [x] 2.1 Create `geomemory-evals/datasets/small/` populated from the
  `geomemorytest/data/` fixture corpus (PDFs, docx, ipynb, py, md, Landsat
  GeoTIFF), plus `queries.yaml` and `manifest.yaml`. Verify: directory exists,
  `queries.yaml` parses, and every source is a pipeline-accepted format.
- [x] 2.2 Create `geomemory-evals/datasets/medium/`, `geospatial/`, and `temporal/`
  with placeholder `queries.yaml` files documenting intended coverage. Verify:
  each directory is recognized as a valid dataset by the dataset loader.
- [x] 2.3 Add `geomemory-evals/` to the project `.gitignore` so datasets, scratch
  workspaces, and run artifacts are all local-only. Verify: `git status` does not
  track the directory.

## 3. Pipeline statistics

- [x] 3.1 Implement `src/geomemory/eval/pipeline_stats.py` with a `collect_stats(conn, path)`
  function querying `asset_revision`, `segment`, `embedding_record`, `entity`,
  and `relation` tables and walking the workspace directory for storage size.
  Verify: returns all eight numeric fields from the spec schema.
- [x] 3.2 Add a `pipeline_stats()` facade method on `GeoMemory` (workspace.py) that
  delegates to the module. Verify: calling it on a fresh workspace returns all-zero
  counts.
- [x] 3.3 Add a unit test asserting the eight-field schema and numeric JSON types.
  Verify: `pytest` passes.

## 4. Run storage

- [x] 4.1 Implement `src/geomemory/eval/run_store.py` with `RunStore(base_dir)` exposing
  `write_run(dataset, benchmark, stats, rows)` and `read_run(dataset, timestamp)`.
  Verify: writes `runs/<dataset>/<timestamp>/stats.json` and `<benchmark>.json` with
  `name`, `config`, `metrics`, `rows`.
- [x] 4.2 Wire `BenchmarkRunner.run` to persist per-query rows via `RunStore` so
  `eval run` writes artifacts alongside its aggregated metrics. Verify: after a
  benchmark run, the run directory exists on disk and `rows` contains per-query
  retrieved ids, scores, metadata, and response.
- [x] 4.3 Add a test asserting run artifacts are immutable (a second run writes a
  new directory, never mutating the first). Verify: `pytest` passes.

## 5. CLI: stats, rebuild, compare

- [x] 5.1 Add `geomemory eval stats <dataset>` to `eval_cmd.py`: ingests the dataset
  into a scratch workspace under `geomemory-evals/workspaces/<dataset>/`, collects
  stats, and writes `stats.json`. Verify: running it on `datasets/small` prints all
  eight stats and creates the artifact.
- [x] 5.2 Add `geomemory eval rebuild <dataset>`: deletes and recreates the scratch
  workspace, re-ingests via the production path, and emits stats (no benchmark
  rerun). Verify: a second invocation reproduces identical stats on a clean machine.
- [x] 5.3 Add `geomemory eval compare <run_a> <run_b>`: diffs `stats.json` and per-query
  rows, prints a JSON diff and text summary, and exits non-zero on any detected
  difference. Verify: comparing two identical runs exits 0; comparing runs with
  differing chunk counts exits non-zero and reports the delta.
- [x] 5.4 Add CLI tests for all three new subcommands under `geomemorytest/`. Verify:
  `pytest geomemorytest` passes.

## 6. Validation

- [x] 6.1 Run `ruff check` and `mypy --strict` over `src/` and confirm no new
  errors. Verify: both commands exit 0.
- [x] 6.2 Run `pytest geomemorytest -q` and confirm the full suite passes. Verify:
  exit 0 with no failures.
- [x] 6.3 Execute `geomemory eval rebuild datasets/small` end-to-end and confirm
  stats are emitted and reproducible. Verify: manual run, artifacts present.