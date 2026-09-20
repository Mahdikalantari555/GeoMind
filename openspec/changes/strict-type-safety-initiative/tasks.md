## 1. Add py.typed markers

- [ ] 1.1 Create empty file `libs/geomemory/src/geomemory/py.typed`
- [ ] 1.2 Create empty file `libs/geoagent/src/geoagent/py.typed`
- [ ] 1.3 Create empty file `libs/geolearn/src/geolearn/py.typed`
- [ ] 1.4 Create empty file `libs/data_engine/src/data_engine/py.typed`
- [ ] 1.5 Verify: `mypy --strict server/src/` no longer reports import-untyped errors for geoagent modules

## 2. Fix geomemory mypy errors (65 errors across 31 files)

### 2a. no-any-return errors (~12)
- [ ] 2a.1 `qa/api_backend.py:76` — narrow Any return type
- [ ] 2a.2 `index/sqlite_vec_backend.py:150` — narrow return type
- [ ] 2a.3 `services/index_service.py:214` — narrow return type
- [ ] 2a.4 `services/index_service.py:348` — narrow return type
- [ ] 2a.5 Remaining no-any-return errors — fix each with proper return type annotation

### 2b. arg-type Literal vs str (~6)
- [ ] 2b.1 `core/workspace.py:278` — Asset.kind accepts str from _kind_for_mime(); change to Literal type or add cast with justification
- [ ] 2b.2 `ingest/pipeline.py:133` — same pattern
- [ ] 2b.3 `ingest/pipeline.py:296` — same pattern
- [ ] 2b.4 `storage/repositories/entity_repo.py:45` — Entity.kind same issue
- [ ] 2b.5 Remaining arg-type errors

### 2c. union-attr / attr-defined (~5)
- [ ] 2c.1 `core/workspace.py:338` — segment_ids None-safety (also covered by retrieval-and-index-correctness change)
- [ ] 2c.2 `core/workspace.py:380` — similar pattern
- [ ] 2c.3 `core/workspace.py:387` — similar pattern
- [ ] 2c.4 `ingest/vision_embed.py:89` — dimension bug (also covered by retrieval-and-index-correctness)
- [ ] 2c.5 `rs/raster/tiler.py:82` — fix or suppress with justification

### 2d. Protocol mismatches (~8)
- [ ] 2d.1 `index_service.py:354-373` — SqliteVecBackend.load() and VectorBackend.load() signatures don't match StorageBackend protocol
- [ ] 2d.2 Align all backend load() signatures to the protocol
- [ ] 2d.3 Remaining protocol errors

### 2e. Miscellaneous (~34)
- [ ] 2e.1 Fix remaining assignment, no-redef, and other errors file by file
- [ ] 2e.2 For third-party stub issues (shapely, geopandas, rasterio, fitz), add targeted `# type: ignore` with comment justification rather than global suppression

## 3. Fix data_engine broken references

- [ ] 3.1 Identify all references to non-existent `PipelineSettings` — find the actual class name and update
- [ ] 3.2 Identify all references to non-existent `process_scene` — find the actual method name and update
- [ ] 3.3 Identify all references to non-existent `AnchorPixelManager` — find the actual class name (`AnchorPixel`) and update
- [ ] 3.4 Run `mypy --strict libs/data_engine/src/` and categorize remaining errors by severity
- [ ] 3.5 Fix highest-impact errors first (those that cause runtime ImportErrors)

## 4. Enable full server strict checking

- [ ] 4.1 After all py.typed markers are in place and geomemory errors are fixed, remove `disable_error_code = ["import-untyped"]` from `server/pyproject.toml`
- [ ] 4.2 Run `mypy --strict server/src/` — expect zero errors
- [ ] 4.3 If new errors appear, fix them before proceeding

## 5. Verification

- [ ] 5.1 Run `conda run -n geospatial mypy --strict libs/geomemory/src/` — expect 0 errors
- [ ] 5.2 Run `conda run -n geospatial mypy --strict libs/geoagent/src/` — expect 0 errors
- [ ] 5.3 Run `conda run -n geospatial mypy --strict libs/geolearn/src/` — expect 0 errors
- [ ] 5.4 Run `conda run -n geospatial mypy --strict server/src/` — expect 0 errors
- [ ] 5.5 Run `conda run -n geospatial pytest libs/geomemory/tests -q` — all tests pass
- [ ] 5.6 Run `conda run -n geospatial pytest libs/geoagent/tests -q` — all tests pass
- [ ] 5.7 Run `conda run -n geospatial ruff check libs/geomemory/src libs/geoagent/src libs/geolearn/src libs/data_engine/src server/src` — no new violations
