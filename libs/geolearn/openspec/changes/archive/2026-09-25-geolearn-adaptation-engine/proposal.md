## Why

GeoLearn's mission is continuous, trustworthy adaptation of remote sensing foundation model representations. To deliver reliable stress differentiation across changing growing seasons without requiring cloud deep learning infrastructure, three core capabilities must be completed:
1. **Calibrated Confidence & Abstention (#21)**: Raw classifier outputs are frequently overconfident. Isotonic calibration and Shannon entropy uncertainty modeling ensure the system reliably abstains (`abstain=True`) on ambiguous or unseen stress patterns.
2. **Facade-Driven Feedback Pipeline with Rollback (#15)**: Verified researcher feedback must trigger incremental `partial_fit()` updates through clean GeoMemory facade calls. Furthermore, if feedback is subsequently revoked, GeoLearn must support deterministic rollback to previous model snapshots.
3. **Seasonal Concept Drift Detection (#12)**: As crop phenology advances across the growing season, reflectance distributions shift. The Page-Hinkley statistical test enables the system to detect temporal concept drift and alert researchers or adapt weights automatically.

Completing these capabilities consolidates GeoLearn's architecture, retires the transitional roadmap, and elevates GeoLearn into a production-grade adaptation engine.

## What Changes

- **Calibrated Uncertainty Modeling (`geolearn.confidence`, `geolearn.calibration`)**:
  - Implement isotonic regression calibration curves mapping raw classifier decision scores to empirical probabilities.
  - Calculate normalized Shannon entropy to quantify epistemic uncertainty.
  - Trigger explicit abstention in `PredictionResult` when uncertainty exceeds thresholds or confidence is uncalibrated.
- **Feedback-to-Training Pipeline with Rollback (`geolearn.training_pipeline`)**:
  - Connect verified candidate memories from GeoMemory facade into incremental `partial_fit()` weight updates.
  - Link training batches to `ModelVersionManager` snapshots in `geolearn.db` to enable automated rollback when feedback items are revoked.
- **Online Learning and Drift Detection (`geolearn.streaming`, `geolearn.drift`)**:
  - Implement the Page-Hinkley cumulative sum algorithm to detect temporal distribution shifts in streaming classification errors.
  - Support sliding window streaming updates for seasonal phenology progression.
- **Documentation & Roadmap Retirement**:
  - Remove `libs/geolearn/docs/phase3-roadmap.md`.
  - Update `libs/geolearn/README.md` and module docstrings to reflect full architectural completeness.

## Capabilities

### New Capabilities
- `confidence-and-uncertainty`: Calibrated confidence estimation, Shannon entropy uncertainty, and reliable abstention.
- `feedback-training-pipeline`: Incremental model updates from GeoMemory feedback with snapshot rollback.
- `online-learning-drift`: Page-Hinkley drift detection and seasonal streaming adaptation.

## Impact

- `libs/geolearn/src/geolearn`: Enhances `confidence.py`, `calibration.py`, `training_pipeline.py`, `streaming.py`, `drift.py`, and `versioning.py`.
- `libs/geolearn/docs`: Retires `phase3-roadmap.md`, references `VISION.md`, and updates `README.md`.
- `libs/geolearn/tests`: Comprehensive unit test coverage for calibration, feedback ingestion, rollback, and drift detection.
