## 1. GeoMemory Facade Type Fix

- [x] 1.1 Add `from collections.abc import Sequence` to `libs/geomemory/src/geomemory/core/workspace.py` and verify `ruff check libs/geomemory/src/geomemory/core/workspace.py` and `mypy` pass without `Sequence` undefined errors.

## 2. Geospatial Core Spectral & GIS Enhancements

- [x] 2.1 Update `savi` signature in `libs/geospatial_core/src/geospatial_core/spectral.py` to `(nir, red, light_coeff=0.5, nodata=np.nan)` and update `compute_spectral_index` dispatch; verify `test_ndwi_and_savi` in `libs/geospatial_core/tests/test_core.py`.
- [x] 2.2 Add interval validation `min < max` in `reclassify_array` in `libs/geospatial_core/src/geospatial_core/gis.py`; add unit test for invalid rule rejection.
- [x] 2.3 Refactor `polygon_area_deg2` and `geodesic_polygon_area_m2` in `libs/geospatial_core/src/geospatial_core/gis.py` to handle 3D coordinates `[x, y, z]` and subtract interior hole ring areas; add unit tests covering 3D coordinates and polygons with cutouts.

## 3. Data Engine Consumer Alignment

- [x] 3.1 Update `raw_savi = geo_savi(nir.values, red.values, light_coeff=L)` in `libs/data_engine/src/data_engine/surface/vegetation.py` to match the new `(nir, red)` parameter order; verify with `pytest libs/data_engine/tests/test_surface_vegetation.py`.

## 4. GeoLearn Confidence Calibration & Drift Detector

- [x] 4.1 Update probability calibration rescaling in `ConfidenceModel.evaluate` in `libs/geolearn/src/geolearn/confidence.py` so the winning class probability is pinned to `cal_max` and remaining probability mass `(1.0 - cal_max)` is distributed proportionally among non-winning classes; add unit test verifying maximum class probability matches `cal_max`.
- [x] 4.2 Update `PageHinkley.update` in `libs/geolearn/src/geolearn/drift.py` to reset `n_instances = 0` and reinitialize `mean = x` when drift is triggered; verify drift recovery in `libs/geolearn/tests/test_drift.py`.

## 5. GeoLearn Model Versioning, Rollback & Streaming

- [x] 5.1 Update `ModelVersionManager.rollback_to` in `libs/geolearn/src/geolearn/versioning.py` to include `sub_region` when updating `classifier_state`.
- [x] 5.2 Update `ModelVersionManager.rollback_feedback` in `libs/geolearn/src/geolearn/versioning.py` to handle `first_bad_ver == 1` by deactivating/resetting the active model state.
- [x] 5.3 Update `TrainingPipeline.rollback_feedback` in `libs/geolearn/src/geolearn/training_pipeline.py` to delete rolled-back candidate IDs from `trained_candidates` in `geolearn.db`; add unit test in `libs/geolearn/tests/test_training_pipeline.py`.
- [x] 5.4 Deduplicate `StreamingWindow` by removing the redundant class in `libs/geolearn/src/geolearn/online.py` and re-exporting `from geolearn.streaming import StreamingWindow`.

## 6. End-to-End Verification

- [x] 6.1 Run test suites across `geospatial_core`, `geolearn`, `geomemory`, `data_engine`, and `server`; verify all tests pass.
- [x] 6.2 Run static analysis (`ruff check` and `mypy --strict`) across all modified libraries; verify zero errors.
