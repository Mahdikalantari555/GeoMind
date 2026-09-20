## Context

`Workspace.stats()` in `core/workspace.py` is called via `GET /api/v1/workspace/stats` and `GET /api/v1/doctor`. It iterates over all revision_ids and executes:
```sql
SELECT COUNT(*) FROM segment WHERE revision_id = ?
SELECT COUNT(*) FROM raster_scene WHERE revision_id = ?
SELECT COUNT(*) FROM vector_layer WHERE revision_id = ?
```
once per revision. For 100 assets this means 300+ individual queries, each round-tripping through SQLite.

The fix uses `GROUP BY revision_id` to aggregate all counts in 3 queries total.

## Goals / Non-Goals

**Goals:**
- Reduce `stats()` from O(N×3) queries to exactly 3 queries regardless of asset count
- Preserve exact same return dict keys and values
- Add a benchmark-style test that verifies the query count improvement

**Non-Goals:**
- Adding caching to stats results (future enhancement)
- Restructuring the stats endpoint response shape
- Optimizing the other SQL queries in stats() (collection/asset counts are already single queries)

## Decisions

### D1: GROUP BY instead of per-row COUNT
**Choice**: Three aggregated queries replacing the loops.
**Rationale**: SQLite GROUP BY is highly optimized and returns results in a single pass. The query plan for `SELECT revision_id, COUNT(*) FROM segment GROUP BY revision_id` uses the existing index on `revision_id` if present, or falls back to a table scan — both faster than N individual point lookups.

### D2: Build counts dict in Python, then merge
**Choice**: Fetch grouped results into dicts, then iterate over revision_ids to build the final stats.
**Rationale**: Keeps the aggregation logic in Python (same pattern as existing code) while eliminating the query loop. Easier to review and test than a complex single SQL statement.
