## 1. Fix vision embedding dimension bug

- [x] 1.1 In `libs/geomemory/src/geomemory/ingest/vision_embed.py:89`, replace `int(index.ids()[0].shape[-1])` with a correct dimension read — either from `index.vectors(0).shape[-1]` if available, or from the embedder's configured output dimension
- [x] 1.2 Add a fallback: if dimension cannot be determined, use the known OLMoEarth Nano dimension (768) and log `logger.warning("could not determine vision embedding dimension, defaulting to 768")`
- [x] 1.3 Write a unit test that mocks the image index and verifies the dimension is read correctly from vector data, not from IDs

## 2. Fix segment_ids null-safety

- [x] 2.1 In `libs/geomemory/src/geomemory/core/workspace.py`, locate line ~338 where `segment_ids` is used after a conditional assignment
- [x] 2.2 Ensure `segment_ids: list[str] = []` is initialized BEFORE any branch that might set it to None
- [x] 2.3 Write a unit test that simulates `_segments_for_revision()` returning None and verifies no AttributeError occurs

## 3. Fix zero-vector image search fallback

- [x] 3.1 In `libs/geomemory/src/geomemory/index/image_backend.py`, locate the `_query_vector()` zero-vector fallback
- [x] 3.2 Replace the zero-vector search with an early return of `[]` (empty hits) and a `logger.warning()` explaining why
- [x] 3.3 Verify that text/dense search results are still returned normally when image search abstains (graceful degradation)
- [x] 3.4 Write a unit test: mock the vision embedder to raise ModelNotLoadedError, assert `_image_search()` returns `[]` and logs a warning

## 4. Unify SearchService

- [x] 4.1 Grep the monorepo for imports of `geomemory.services.search_service`: `grep -rn "geomemory.services.search_service" . --include="*.py"`
- [x] 4.2 If zero external callers: delete `libs/geomemory/src/geomemory/services/search_service.py`
- [x] 4.3 If any callers exist: update them to import from `geomemory.retrieval.search_service` instead
- [x] 4.4 Verify `Workspace.search()` passes `modalities` and `modality_weight` through to the retrieval service

## 5. Verification

- [x] 5.1 Run `conda run -n geospatial pytest libs/geomemory/tests/unit/test_vision*.py -v --tb=short` — new tests must pass
- [x] 5.2 Run `conda run -n geospatial pytest libs/geomemory/tests/ -q --tb=short` — all 503 tests must pass
- [x] 5.3 Run `conda run -n geospatial ruff check libs/geomemory/src/geomemory/ingest/ libs/geomemory/src/geomemory/core/workspace.py libs/geomemory/src/geomemory/index/image_backend.py`
- [x] 5.4 Run `conda run -n geospatial mypy --strict libs/geomemory/src/geomemory/ingest/vision_embed.py libs/geomemory/src/geomemory/core/workspace.py libs/geomemory/src/geomemory/index/image_backend.py`
