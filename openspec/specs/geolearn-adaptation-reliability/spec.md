# geolearn-adaptation-reliability Specification

## Purpose

Ensures mathematical correctness of confidence calibration, drift detection state stability, and reliable feedback rollback within GeoLearn.

## Requirements

### Requirement: Confidence probability calibration preserves calibrated scale
The `ConfidenceModel.evaluate` method SHALL output `calibrated_probabilities` where the maximum class probability equals the calibrated score `cal_max`, while distributing the remaining probability mass proportionally across other classes such that class probabilities sum to 1.0.

#### Scenario: Calibrated probability preservation
- **WHEN** raw class probabilities have maximum value 0.8 and calibration maps this to 0.5
- **THEN** the resulting `calibrated_probabilities` has maximum class probability exactly equal to 0.5, and the sum over all classes equals 1.0

### Requirement: PageHinkley drift detector state reinitialization
The `PageHinkley` drift detector SHALL reset its sample counter `n_instances` to 0 and reinitialize running mean upon detecting concept drift, preventing false positive alarms from immediately triggering on subsequent samples.

#### Scenario: Stationary post-drift behavior
- **WHEN** drift is detected and followed by a stationary sequence from the new distribution
- **THEN** the detector does not immediately report drift on the subsequent observations until `n_instances >= min_instances` and deviation exceeds threshold again

### Requirement: Feedback rollback and candidate tracking lifecycle
The `ModelVersionManager` and `TrainingPipeline` SHALL support rolling back models that were trained on revoked feedback, handling version 1 gracefully, preserving `sub_region` metadata in `classifier_state`, and clearing rolled-back candidate IDs from `trained_candidates` to prevent feedback starvation.

#### Scenario: Rollback of initial model version 1
- **WHEN** revoked feedback was incorporated into model version 1
- **THEN** rollback removes or deactivates version 1 without silent failure

#### Scenario: Hierarchical sub-region preservation on rollback
- **WHEN** a classifier associated with a hierarchical key `(crop, region, sub_region)` is rolled back
- **THEN** the updated `classifier_state` row preserves `sub_region` accurately

#### Scenario: Candidate ID un-tracking upon rollback
- **WHEN** candidate feedback is revoked and corresponding model versions are rolled back
- **THEN** candidate IDs associated with the rolled-back versions are removed from `trained_candidates` so eligible candidates can be retrained in future cycles

### Requirement: Single streaming window canonical implementation
The `StreamingWindow` data structure SHALL have a single implementation in `geolearn.streaming` and be re-exported by `geolearn.online`, ensuring consistent type annotations, array conversions, and incremental classifier updates.

#### Scenario: Streaming window import consistency
- **WHEN** downstream code imports `StreamingWindow` from `geolearn.online` or `geolearn.streaming`
- **THEN** the identical class is referenced supporting `add`, `get_arrays`, and `update_classifier`