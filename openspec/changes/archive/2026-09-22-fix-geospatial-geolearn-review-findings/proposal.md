## Why

Recent architectural changes unified geospatial calculations into `geospatial_core` and extended `geolearn` online adaptation and `geomemory` candidate memory facades. Code review identified 1 CRITICAL static type error (`Sequence` undefined in `Workspace`), 6 HIGH severity algorithmic, API, and state integrity defects (normalization canceling probability calibration, inverted `savi` signature, silent rollback failure on version 1, unhandled 3D coordinates, post-drift state pollution, lost `sub_region` on rollback), and 3 MEDIUM maintainability/robustness issues. Resolving these defects now prevents downstream crashes, incorrect spectral computations, and corrupted model state during adaptive learning.

## What Changes

- **Fix Missing Facade Imports**: Add `from collections.abc import Sequence` to `geomemory.core.workspace` ensuring runtime type introspection and mypy/ruff checks succeed.
- **Correct SAVI Parameter Signature**: Standardize `savi(nir, red, ...)` to place `nir` first matching `ndvi` and `evi`, and update callers across `geospatial_core` and `data_engine`. (**BREAKING** for direct callers of `savi` with positional arguments).
- **Fix Probability Calibration Normalization**: Rework `ConfidenceModel.evaluate` so calibrating top-class probability pins the winning class probability to `cal_max` and scales remaining probabilities across non-winning classes rather than dividing by full sum and canceling calibration.
- **Robust 3D GeoJSON & Polygon Holes in GIS Area**: Update `polygon_area_deg2` and `geodesic_polygon_area_m2` to safely index `p[0], p[1]` ignoring optional elevation components, and account for interior rings (holes).
- **Add Interval Validation in `reclassify_array`**: Enforce `r["min"] < r["max"]` for each rule.
- **Fix PageHinkley Drift State Reset**: Reset `n_instances` and reinitialize `mean` upon drift detection to avoid cascading false alarms.
- **Fix Feedback Rollback & Candidate Lifecycle**: In `ModelVersionManager.rollback_feedback`, handle `first_bad_ver == 1` properly, preserve `sub_region` during rollback in `classifier_state`, and remove rolled-back candidate IDs from `trained_candidates` so valid feedback is not orphaned.
- **Deduplicate `StreamingWindow`**: Remove the duplicate implementation in `geolearn.online` and import from `geolearn.streaming`.

## Capabilities

### New Capabilities
- `geolearn-adaptation-reliability`: Establishes requirements for accurate probability calibration, concept drift state management, and reliable version rollback for online learning models.

### Modified Capabilities
- `data-engine-gis`: Refines requirements for spectral index signatures (`savi`), robust GeoJSON coordinate parsing (3D and polygon holes), and interval validation.
- `candidate-memory-completion`: Clarifies strict type contract and multi-state querying on the public `GeoMemory` facade.

## Impact

- `libs/geomemory`: Resolves type checking and runtime `NameError` in `Workspace.list_candidate_memories`.
- `libs/geospatial_core`: API signature alignment for `savi(nir, red, ...)`, geometry parsing robustness in `gis.py`.
- `libs/data_engine`: Caller update in `vegetation.py` for new `savi` signature.
- `libs/geolearn`: Probability calibration output fidelity in `confidence.py`, drift detector reliability in `drift.py`, versioning and feedback rollback state consistency in `versioning.py` and `training_pipeline.py`.
