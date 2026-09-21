## 1. Aggregate segment counts

- [x] 1.1 In `libs/geomemory/src/geomemory/core/workspace.py`, locate the `stats()` method (~line 1185); replace the per-revision `SELECT COUNT(*) FROM segment WHERE revision_id = ?` loop with a single `SELECT revision_id, COUNT(*) AS c FROM segment GROUP BY revision_id` query and build a `{rev_id: count}` dict
- [x] 1.2 Verify: the dict keys are the same revision_ids as before, and values match per-revision COUNT results

## 2. Aggregate raster_scene and vector_layer counts

- [x] 2.1 Replace the nested per-revision loop over `("raster_scene", "vector_layer")` (lines ~1194–1206) with two separate `GROUP BY` queries: `SELECT revision_id, COUNT(*) FROM raster_scene GROUP BY revision_id` and the same for `vector_layer`
- [x] 2.2 Build separate dicts for scene_count and vector_count keyed by revision_id, then sum across revisions in the return dict

## 3. Verify correctness

- [x] 3.1 Write a unit test: create a workspace with 5 assets (some with revisions, some without), call `stats()`, and assert the returned `segment_count`, `scene_count`, and `layer_count` match manually computed values
- [x] 3.2 Run `conda run -n geospatial pytest libs/geomemory/tests -q --tb=short` — expect 503 passed
- [x] 3.3 Run `conda run -n geospatial ruff check libs/geomemory/src/geomemory/core/workspace.py` — clean
- [x] 3.4 Update `tasks/todo.md` checkboxes to reflect completion status
