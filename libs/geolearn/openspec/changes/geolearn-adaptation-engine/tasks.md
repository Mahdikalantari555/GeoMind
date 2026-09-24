## 1. Confidence & Uncertainty Modeling (#21)

- [ ] 1.1 Implement `IsotonicCalibrator` in `libs/geolearn/src/geolearn/calibration.py` with test suite
- [ ] 1.2 Implement Shannon entropy uncertainty calculation in `libs/geolearn/src/geolearn/confidence.py`
- [ ] 1.3 Wire calibrated probabilities and abstention logic into `PredictionResult` with unit tests

## 2. Feedback-to-Training Pipeline & Rollback (#15)

- [ ] 2.1 Refactor `TrainingPipeline.run()` to consume candidate memories via GeoMemory facade
- [ ] 2.2 Implement feedback batch tagging and rollback support in `ModelVersionManager`
- [ ] 2.3 Add tests verifying model weight update and rollback on feedback revocation in `tests/test_training_pipeline.py`

## 3. Online Learning & Drift Detection (#12)

- [ ] 3.1 Implement `PageHinkley` drift detector in `libs/geolearn/src/geolearn/drift.py`
- [ ] 3.2 Enhance `libs/geolearn/src/geolearn/streaming.py` with sliding window streaming updates
- [ ] 3.3 Add drift simulation and streaming window unit tests in `tests/test_drift.py`

## 4. Documentation & Cleanup

- [ ] 4.1 Remove `libs/geolearn/docs/phase3-roadmap.md`
- [ ] 4.2 Update `libs/geolearn/README.md` and verify all tests pass with `conda run -n geospatial pytest libs/geolearn/tests`
