## Context

See proposal.md for motivation. This design covers the implementation approach
for the eval framework layered on the existing GeoMemory surface.

Existing building blocks reused without duplication:
- `geomemory.cli.main:cli` — command group; new subcommands attach to the existing
  `eval` group (`eval_cmd.py`).
- `BenchmarkRunner` (`eval/runner.py`) — retrieval/QA metric aggregation; reused
  unchanged for `eval run`.
- `GeoMemory.ingest` / `GeoMemory.search` / `GeoMemory.ask` — production code paths;
  the framework calls these, never reimplementing them.
- `Pipeline.ingest` / loader registry — production ingestion; the ShapefileLoader
  plugs into `default_loader_registry()`.

## Goals / Non-Goals

**Goals:**
- Repeatable, reproducible pipeline validation on in-repo datasets.
- Scratch-workspace isolation so rebuild never touches the user's real workspace.
- Stable, diff-friendly run artifact layout.

**Non-Goals:**
- LLM reasoning quality measurement.
- Automatic scientific answer evaluation.
- Public leaderboard or CI/CD integration (deferred).

## Decisions

### D1: Extend `geomemory eval`, do not add a new tool
**Decision:** New subcommands (`stats`, `rebuild`, `compare`) attach to the
existing `eval` group; no new `geomemory-eval` entry point.

**Alternatives:** A standalone `geomemory-eval` CLI would duplicate the
`BenchmarkRunner`/`load_benchmark`/metrics surface. The existing commands
(`ingest`, `search`, `doctor`) already sit at the same CLI level, so rebuild/compare
fit naturally as evaluation operations.

### D2: Scratch workspace under `geomemory-evals/workspaces/<dataset>/`
**Decision:** Rebuild creates and re-creates a throwaway workspace inside the
eval tree, never the user's configured workspace.

**Rationale:** Rebuild deletes the database by design. Sandbox isolation is the
only safe way to honor that without risking user data.

### D3: Rebuild stops at stats
**Decision:** `eval rebuild` runs ingest → stats only; it does not rerun benchmark
queries.

**Rationale:** Rebuild validates ingestion determinism and schema migration, not
query quality. Benchmark reruns are `eval run`'s job and can be chained
manually. Keeps rebuild fast and focused.

### D4: Single per-benchmark result file, not one file per query
**Decision:** Each run writes `runs/<dataset>/<timestamp>/<benchmark>.json`
containing `name`, `config`, `metrics`, and `rows` (per-query). Stats live in
`stats.json` at the same level.

**Rationale:** One file per query explodes on large benchmarks and makes diffing
awkward. A single file with a `rows` array is diff-friendly and easy to load.

**Alternative:** One file per query (as the spec's example suggests) — rejected for
the explosion/awkward-diff reasons above.

### D5: Reuse `geomemorytest/data/` as the `small` dataset baseline
**Decision:** The `small` dataset reuses the existing fixture corpus (PDFs, docx,
ipynb, py, md, Landsat GeoTIFF). Users add new papers/data under
`medium/`, `geospatial/`, `temporal/`.

**Rationale:** Avoids duplicating ~20MB of already-validated fixtures and keeps
eval independent of test changes by pinning a snapshot rather than symlinking.

### D6: Shapefile loader gated on the `rs` extra
**Decision:** `ShapefileLoader` requires `geopandas`/`shapely` (in the `rs`
extra). Import raises a clear `RuntimeError` naming the missing dependency.

**Rationale:** Consistent with `GeoTiffLoader`, which is also gated on `rs`.

## Risks / Trade-offs

- **[Scratch workspace collision]** Rebuild targets a fixed path; concurrent
  rebuilds of the same dataset could clash. → Serialize per-dataset rebuilds with
  a lock file inside `geomemory-evals/workspaces/`.
- **[Binary dataset growth]** GeoTIFF/PDF assets bloat the repo. → Keep datasets
  small; document the size bound in the dataset manifest guidance.
- **[Stats staleness]** `stats()` queries live tables; a rebuild that errors
  mid-ingest could emit partial stats. → Emit stats only after the final job
  completes; on error, write `stats.json` with an `error` field instead.
- **[Diff noise]** Per-query retrieval diffs are noisy when retrieval is
  non-deterministic. → Comparison reports set differences, not exact ordering,
  and exits non-zero only on set changes plus stats drift.

## Migration Plan

- No breaking API changes. New CLI subcommands are additive.
- `geomemory-evals/` is new; `workspaces/` and `runs/` are gitignored.
- Existing `geomemory eval run` behavior is unchanged.

## Open Questions

- Should `eval rebuild` optionally chain into `eval run` for a full end-to-end
  validation? Deferred — the spec settles on stats-only; revisit if users want it.
- Should comparison support fuzzy query matching (e.g. normalized text) instead of
  exact string equality? Deferred — exact match is the simple, predictable default.