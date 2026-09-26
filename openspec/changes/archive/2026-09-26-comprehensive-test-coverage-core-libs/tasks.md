## 1. Geospatial Core Coverage (>95%)

- [x] 1.1 Add unit tests in `libs/geospatial_core/tests/test_core.py` covering `polygonize_array` (with masks, nodata, tolerance simplification).
- [x] 1.2 Add tests for `polygon_area_deg2` and `geodesic_polygon_area_m2` with `MultiPolygon`, polygon holes, and 3D coordinates.
- [x] 1.3 Add tests for `parse_epsg` with `pyproj.CRS` and `rasterio.crs.CRS` objects.
- [x] 1.4 Verify `pytest libs/geospatial_core/tests --cov=libs/geospatial_core/src/geospatial_core` reports >95% coverage.

## 2. GeoDomain Coverage (>95%)

- [x] 2.1 Add unit tests in `libs/geodomain/tests/` covering temporal intervals, invalid bounds, and label hierarchy conversions.
- [x] 2.2 Verify `pytest libs/geodomain/tests --cov=libs/geodomain/src/geodomain` reports >95% coverage.

## 3. GeoLearn Coverage (>95%)

- [x] 3.1 Add unit tests for `IsotonicCalibrator.predict_proba` with Platt scaling, constant, and empty array cases.
- [x] 3.2 Add unit tests for `RiverDriftDetector` fallback branches when river is absent/present in `libs/geolearn/tests/test_drift.py`.
- [x] 3.3 Add unit tests for `EdgeLoader` model serialization and error branches in `libs/geolearn/tests/test_edge.py`.
- [x] 3.4 Add unit tests for `StreamingWindow` FIFO eviction and batch updates in `libs/geolearn/tests/test_drift.py`.
- [x] 3.5 Verify `pytest libs/geolearn/tests --cov=libs/geolearn/src/geolearn` reports >95% coverage.

## 4. GeoAgent Coverage (>95%)

- [x] 4.1 Create `libs/geoagent/tests/test_cli.py` using `click.testing.CliRunner` to test `geoagent.cli` subcommands (`run`, `interactive`, `inspect`).
- [x] 4.2 Add unit tests in `libs/geoagent/tests/test_geolearn_tools.py` for GeoLearn predictor and adaptation tool handlers.
- [x] 4.3 Add unit tests in `libs/geoagent/tests/test_llm.py` for `openai_compat.py` error and streaming token parsing.
- [x] 4.4 Verify `pytest libs/geoagent/tests --cov=libs/geoagent/src/geoagent` reports >95% coverage.

## 5. GeoMemory Coverage (>95%)

- [x] 5.1 Add unit tests in `libs/geomemory/tests/unit/test_cli.py` using `CliRunner` for commands (`chat`, `inspect`, `reindex`, `eval_cmd`, `app`, `feedback`).
- [x] 5.2 Add unit tests for unexercised `Workspace` search filters, candidate memory queries, and export operations in `libs/geomemory/tests/unit/test_workspace.py`.
- [x] 5.3 Add unit tests for vector backends (`sqlite_vec_backend`, `numpy_backend`, `vector_backend`) compaction and deletion paths.
- [x] 5.4 Add unit tests for file loaders (`code`, `shapefile`, `pdf`, `opendataloader_pdf`) handling valid files and corrupt inputs.
- [x] 5.5 Verify `pytest libs/geomemory/tests --cov=libs/geomemory/src/geomemory` reports >95% coverage.

## 6. Full Suite Gate & CI Verification

- [x] 6.1 Execute combined pytest command across all 5 libraries; verify each package meets or exceeds the 95% threshold and zero failures occur.
