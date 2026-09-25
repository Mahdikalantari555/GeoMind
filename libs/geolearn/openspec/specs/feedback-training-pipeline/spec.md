# feedback-training-pipeline Specification

## Purpose
Wires verified candidate memories from GeoMemory into incremental model updates, tracking training history and enabling deterministic snapshot rollbacks on feedback revocation.

## Requirements

### Requirement: Facade-Driven Incremental Training
The `TrainingPipeline` SHALL consume verified candidate memories through GeoMemory facade calls and update SGD/online classifiers via `partial_fit()`, partitioned by `(crop_type, region)` key.

#### Scenario: Incremental batch training
- **WHEN** new verified candidate memories are available in GeoMemory
- **THEN** `TrainingPipeline.run()` updates the corresponding regional classifier weights and increments training counters

### Requirement: Rollback on Feedback Revocation
The `TrainingPipeline` and `ModelVersionManager` SHALL support rolling back to a previous model snapshot when feedback items are marked rejected or revoked.

#### Scenario: Reverting erroneous feedback
- **WHEN** a feedback item used in a prior training cycle is revoked
- **THEN** the model manager restores the snapshot created prior to that training batch
