## Why

`Workspace.stats()` loops over every revision_id in a workspace and issues three separate `SELECT COUNT(*)` queries per revision — one for segments, one for raster_scenes, and one for vector_layers. A workspace with 100 assets generates ~300 serial SELECT statements. This scales linearly and becomes a measurable latency source for production dashboards.

The fix replaces the per-revision loop with three `GROUP BY revision_id` queries, reducing the count from O(N×3) to exactly 3.

## What Changes

- Replace the `segment_ids` COUNT loop in `Workspace.stats()` with a single `SELECT revision_id, COUNT(*) FROM segment GROUP BY revision_id` query
- Replace the `raster_scene` / `vector_layer` COUNT loop with two `GROUP BY` queries
- Preserve the exact same return dict shape and values
- No API change, no schema change, no new dependencies

## Capabilities

### New Capabilities
- *(none — this is a performance optimization, not a behavior change)*

### Modified Capabilities
- *(none — no spec-level requirement is changing; the stats contract remains identical)*

## Impact

- **File modified**: `libs/geomemory/src/geomemory/core/workspace.py` (the `stats()` method, lines ~1171–1206)
- **No API change**: Gateway `GET /api/v1/workspace/stats` response shape is unchanged
- **No test impact expected**: Existing tests assert dict values, not query counts
- **Verifiable**: Before/after query count can be measured with `conn.execute("EXPLAIN ...")` or by counting cursor executions in a test
