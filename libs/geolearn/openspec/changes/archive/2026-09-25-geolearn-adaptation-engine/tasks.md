## 1. Confidence & Uncertainty Modeling (#21)

- [x] 1.1 Implement `IsotonicCalibrator` in `libs/geolearn/src/geolearn/calibration.py` with test suite
- [x] 1.2 Implement Shannon entropy uncertainty calculation in `libs/geolearn/src/geolearn/confidence.py`
- [x] 1.3 Wire calibrated probabilities and abstention logic into `PredictionResult` with unit tests

## 2. Feedback-to-Training Pipeline & Rollback (#15)

- [x] 2.1 Refactor `TrainingPipeline.run()` to consume candidate memories via GeoMemory facade
- [x] 2.2 Implement feedback batch tagging and rollback support in `ModelVersionManager`
- [x] 2.3 Add tests verifying model weight update and rollback on feedback revocation in `tests/test_training_pipeline.py`

## 3. Online Learning & Drift Detection (#12)

- [x] 3.1 Implement `PageHinkley` drift detector in `libs/geolearn/src/geolearn/drift.py`
- [x] 3.2 Enhance `libs/geolearn/src/geolearn/streaming.py` with sliding window streaming updates
- [x] 3.3 Add drift simulation and streaming window unit tests in `tests/test_drift.py`

## 4. Documentation & Cleanup

- [x] 4.1 Remove `libs/geolearn/docs/phase3-roadmap.md`
- [x] 4.2 Update `libs/geolearn/README.md` and verify all tests pass with `conda run -n geospatial pytest libs/geolearn/tests`
