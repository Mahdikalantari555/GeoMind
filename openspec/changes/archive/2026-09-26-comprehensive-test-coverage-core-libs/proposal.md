## Why

Currently, test coverage across core libraries varies significantly (`geodomain` 93%, `geolearn` 88%, `geospatial_core` 81%, `geoagent` 75%, and `geomemory` 72%). Unexercised branches in core execution paths — including spatial polygonization, CLI commands, vector retrieval fallbacks, online adaptation schedulers, and workspace transactions — expose the system to undetected regressions during refactors. Elevating test coverage to >95% across all 5 non-data-engine core libraries (`geospatial_core`, `geodomain`, `geolearn`, `geoagent`, `geomemory`) establishes robust regression defense and production readiness.

## What Changes

- **`geospatial_core` (>95%)**:
  - Add unit tests for `polygonize_array` with/without masks, nodata filtering, and simplify tolerances.
  - Add tests for `MultiPolygon` and geodesic calculations with holes in `polygon_area_deg2` and `geodesic_polygon_area_m2`.
  - Add tests for `parse_epsg` with rasterio/pyproj CRS instances.
- **`geodomain` (>95%)**:
  - Add unit tests for temporal window edge cases, duration computations, and label hierarchy navigation.
- **`geolearn` (>95%)**:
  - Add unit tests covering `IsotonicCalibrator.predict_proba` with Platt, constant, and edge cases.
  - Add unit tests for `StreamingWindow` eviction, arrays, and batch updates.
  - Add unit tests for `RiverDriftDetector` and `SimpleDriftDetector` fallback branches.
  - Add unit tests for `EdgeLoader` model export/load edge cases and adapter wrappers.
- **`geoagent` (>95%)**:
  - Add test suite for `geoagent.cli` commands (`run`, `interactive`, `inspect`).
  - Add tests for `geolearn_tools.py` tool wrappers (retrain, evaluate, predict).
  - Add tests for `openai_compat.py` error and token streaming branches.
- **`geomemory` (>95%)**:
  - Add tests for CLI commands in `libs/geomemory/src/geomemory/cli/commands/` (`chat`, `inspect`, `reindex`, `eval_cmd`, `app`).
  - Add unit tests for unexercised `Workspace` CRUD operations, search filters (spatial/temporal/sensor), and proposal flows.
  - Add unit tests for `sqlite_vec_backend`, `numpy_backend`, and `vector_backend` serialization and compaction routines.
  - Add unit tests for `loaders/code.py`, `loaders/shapefile.py`, `loaders/pdf.py`, and `loaders/opendataloader_pdf.py`.

## Capabilities

### New Capabilities
- `core-libraries-test-coverage`: Normative coverage requirements mandating >95% statement and branch test coverage across `geospatial_core`, `geodomain`, `geolearn`, `geoagent`, and `geomemory`.

## Impact

- `libs/geospatial_core/tests`: Expanded unit test suite.
- `libs/geodomain/tests`: Expanded boundary tests.
- `libs/geolearn/tests`: Comprehensive calibration, drift, and persistence test suite.
- `libs/geoagent/tests`: New CLI and tool runner test suites.
- `libs/geomemory/tests`: New CLI, storage repository, loader, and workspace test suites.
- Production code: Minor testability hooks if required (no breaking architectural changes).
