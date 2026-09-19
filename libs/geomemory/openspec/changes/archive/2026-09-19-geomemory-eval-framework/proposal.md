## Why

GeoMemory has no repeatable way to answer "does it still work on real data?" after
refactors, schema changes, or retrieval-pipeline edits. Existing eval tooling
(`geomemory eval run`, `BenchmarkRunner`, recall@k/MRR/nDCG/QA metrics) measures
*query quality* but not *pipeline health*: there is no dataset harness, no
ingestion statistics capture, no run persistence, and no way to diff two runs.
Every regression check today is ad-hoc and non-reproducible.

## What Changes

- **In-repo eval datasets** under `geomemory-evals/datasets/{small,medium,geospatial,temporal}/`,
  reusing the existing `geomemorytest/data/` fixture corpus as the `small` baseline.
  Each dataset carries a `queries.yaml` of benchmark queries.
- **Pipeline statistics** captured after ingestion: files, documents, chunks,
  embeddings, entities, relations, duration, storage size. Persisted as `stats.json`.
- **Run persistence**: every eval/rebuild run writes artifacts to
  `runs/<dataset>/<timestamp>/` — `stats.json` plus one `<benchmark>.json` with
  per-query rows (query text, retrieved ids, scores, response, metadata).
- **Rebuild validation**: `geomemory eval rebuild <dataset>` deletes and recreates a
  *scratch* workspace under `geomemory-evals/workspaces/<dataset>/`, re-ingests the
  dataset through the production code path, and emits stats. Never touches the
  user's real workspace. Stops at stats (no benchmark rerun).
- **Comparison mode**: `geomemory eval compare <run_a> <run_b>` diffs stats and
  per-query retrieval, surfacing chunk/entity/relation count drift, missing and
  newly-discovered results.
- **Shapefile loader** (`.shp`, requires `rs` extra): routes through the existing
  loader registry so shapefiles ingest without manual GeoJSON conversion.

## Capabilities

### New Capabilities
- `eval-datasets`: in-repo dataset layout, manifest, and per-dataset `queries.yaml` contract
- `pipeline-stats`: ingestion pipeline statistics collection and `stats.json` schema
- `run-storage`: run artifact persistence layout and per-query result schema
- `run-comparison`: two-run diffing with regression surfacing

### Modified Capabilities
- `ingestion`: adds Shapefile to format routing (new loader + registry entry)
- `feedback-evaluation`: extends eval tooling with `stats`, `rebuild`, and `compare`
  commands and per-query artifact emission alongside existing aggregated metrics

## Impact

- **Code**:
  - `src/geomemory/cli/commands/eval_cmd.py` — new `stats`, `rebuild`, `compare` subcommands
  - `src/geomemory/eval/` — new `pipeline_stats.py`, `run_store.py`, `compare.py` modules
  - `src/geomemory/ingest/loaders/shapefile.py` (new) + registry entry in `loaders/__init__.py`
  - `src/geomemory/core/workspace.py` — thin `pipeline_stats()` facade method over existing tables
- **Data**: `geomemory-evals/` directory tree (datasets committed; `workspaces/` and
  `runs/` gitignored)
- **Deps**: shapefile loading requires `geopandas`/`shapely` (already in `rs` extra)
- **APIs**: no breaking changes; all new surface is additive
- **Risks**: scratch-workspace rebuild must be sandboxed from real workspaces;
  binary dataset assets (GeoTIFF/PDF) increase repo size — keep datasets small
