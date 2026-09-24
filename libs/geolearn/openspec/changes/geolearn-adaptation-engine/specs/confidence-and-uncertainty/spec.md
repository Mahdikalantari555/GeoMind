## Purpose

Provides empirical probability calibration via isotonic curves and entropy-based uncertainty quantification, powering reliable abstention in agricultural stress differentiation.

## ADDED Requirements

### Requirement: Isotonic Probability Calibration
The `geolearn.calibration` module SHALL provide an `IsotonicCalibrator` that fits monotonic step-wise calibration functions over validation scores to produce calibrated empirical probabilities.

#### Scenario: Calibrating raw prediction scores
- **WHEN** an uncalibrated classifier score is evaluated
- **THEN** the calibrator maps the score to an empirical probability with bounded error

### Requirement: Entropy-Based Uncertainty & Abstention
The `ConfidenceModel` SHALL compute normalized Shannon entropy across class probability distributions and set `abstain=True` on `PredictionResult` when entropy exceeds a configurable threshold or maximum calibrated probability is below the decision boundary.

#### Scenario: High uncertainty triggers abstention
- **WHEN** an embedding produces near-uniform class probabilities across multiple stress classes
- **THEN** `PredictionResult.abstain` is `True` and the reason identifies high entropy uncertainty
