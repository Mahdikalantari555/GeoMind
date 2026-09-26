## Context

Following the consolidation of geospatial algorithms into `geospatial_core` and the introduction of online model adaptation in `geolearn`, static analysis and detailed review surfaced precision, typing, and state lifecycle issues across four packages (`geomemory`, `geospatial_core`, `data_engine`, and `geolearn`). See `proposal.md` for motivation and issue taxonomy.

## Goals / Non-Goals

**Goals:**
- Eliminate all undefined symbol diagnostics (`Sequence`) in `geomemory.core.workspace` ensuring strict typing compliance.
- Unify spectral index calling conventions across `geospatial_core` and consumers (`data_engine`) so all vegetation index functions accept NIR before Red.
- Ensure probability calibration in `ConfidenceModel.evaluate` preserves calibrated class probability values (`cal_max`) instead of canceling them out during array normalization.
- Make GIS area calculation in `geospatial_core.gis` robust against 3D coordinate arrays `[x, y, z]` and polygon holes.
- Prevent concept drift cascade errors by reinitializing `PageHinkley` detector statistics upon detection.
- Provide reliable model rollback when initial version 1 is tainted, preserve hierarchical `sub_region` in state tracking, and reconcile `trained_candidates`.
- Consolidate `StreamingWindow` to a single source of truth in `geolearn.streaming`.

**Non-Goals:**
- Modifying classifier algorithms (e.g. replacing PassiveAggressive or SGD).
- Altering the SQLite database schemas for `geomemory` or `geolearn`.
- Rewriting underlying RTree/FTS5 indexes or vector embeddings.

## Decisions

### Decision 1: Probability Calibration Rescaling Algorithm
- **Problem**: Multiplying `(row / raw_max) * cal_max` and then dividing by `np.sum(row_cal)` mathematically simplifies to `row / np.sum(row)`, canceling `cal_max`.
- **Choice**: Explicitly set the winning class index `max_idx = argmax(row)` to `cal_max`. Compute the residual probability `1.0 - cal_max`. Proportionally rescale the non-winning classes using their normalized share of the residual:
  ```python
  max_idx = int(np.argmax(row))
  cal_row = np.zeros_like(row)
  cal_row[max_idx] = cal_max
  other_sum = float(np.sum(row)) - raw_max
  if other_sum > 0:
      for i in range(len(row)):
          if i != max_idx:
              cal_row[i] = (row[i] / other_sum) * (1.0 - cal_max)
  elif len(row) > 1:
      # Uniform split among other classes if all non-winning were zero
      fill = (1.0 - cal_max) / (len(row) - 1)
      for i in range(len(row)):
          if i != max_idx:
              cal_row[i] = fill
  ```
- **Alternatives Considered**:
  - Platt/isotonic across all classes individually: Requires multi-output calibration which isn't trained on binary correctness observations.
  - Softmax with temperature scaling: Adds parameter estimation overhead not supported by the existing calibration curve.

### Decision 2: SAVI Parameter Order Alignment
- **Problem**: `savi(red, nir, ...)` takes `red` before `nir`, causing positional callers to invert the vegetation calculation.
- **Choice**: Change signature to `savi(nir: np.ndarray, red: np.ndarray, light_coeff: float = 0.5, nodata: float = np.nan)`. Update callers in `geospatial_core.spectral.compute_spectral_index` and `data_engine.surface.vegetation`.
- **Alternatives Considered**:
  - Keep signature and force keyword-only arguments: Would break existing positional usage in `data_engine` and create non-standard divergence from `ndvi(nir, red)`.

### Decision 3: GeoJSON 3D Coordinates and Hole Processing
- **Problem**: 2-tuple unpacking `for (x1, y1), (x2, y2) in zip(pts, ...)` raises `ValueError` on 3D GeoJSON coordinates. Furthermore, interior rings in Polygon coordinates are ignored.
- **Choice**:
  - Index points as `p[0], p[1]` directly without tuple unpacking.
  - In `polygon_area_deg2` and `geodesic_polygon_area_m2`, compute exterior ring area (`coords[0]`) and subtract all interior hole ring areas (`coords[1:]`).
- **Alternatives Considered**:
  - Rely on shapely `shape(geom).area`: `polygon_area_deg2` is meant to be a lightweight pure-Python/NumPy routine independent of GDAL/GEOS when possible.

### Decision 4: PageHinkley Post-Drift State Reset
- **Problem**: When drift occurs, `sum_val` is reset, but `n_instances` and `mean` retain historical sample counts and pre-drift values, causing immediate repeat detections.
- **Choice**: In `PageHinkley.update`, when drift is detected:
  ```python
  self.drift_detected = True
  self.n_instances = 0
  self.mean = x
  self.sum_val = 0.0
  self.min_sum = 0.0
  ```
- **Alternatives Considered**:
  - Only reset `sum_val`: Led to false positives on subsequent observations in testing.

### Decision 5: Rollback Handling for Version 1 and Candidate Un-tracking
- **Problem**: If bad feedback is in version 1, `target_ver = 0` causes rollback to be silently skipped. Also, rolled back candidate IDs stay in `trained_candidates`.
- **Choice**:
  - If `first_bad_ver == 1`: Remove active model pickle or mark inactive, clearing state in `classifier_state` and recording rollback reason.
  - When rolling back to `target_ver`: Query `model_versions` for all versions `> target_ver`, extract their `feedback_ids`, and execute `DELETE FROM trained_candidates WHERE candidate_id IN (...)` in `geolearn.db`.
  - In `rollback_to`, include `sub_region` in SQL `INSERT OR REPLACE INTO classifier_state`.

## Risks / Trade-offs

- **[Risk] Breaking SAVI positional callers** → Mitigation: Only internal callers exist in the monorepo (`geospatial_core`, `data_engine`), all updated atomically in this change.
- **[Risk] Feedback candidate re-training volume** → Mitigation: Un-tracking rolled-back candidates correctly returns them to the pending queue for re-training with clean labels.
