import numpy as np
import pytest
from geolearn.calibration import (
    CalibrationCurve,
    IsotonicCalibrator,
    compute_final_confidence,
    prediction_entropy,
)
from geolearn.confidence import ConfidenceModel, shannon_entropy
from geolearn.models import PredictionResult


def test_prediction_entropy_bounds():
    assert prediction_entropy([1.0, 0.0, 0.0]) == 0.0
    ent = prediction_entropy([0.33, 0.33, 0.34])
    assert abs(ent - 1.098) < 0.01


def test_shannon_entropy_normalized():
    # 2 classes: [0.5, 0.5] should have normalized entropy = 1.0
    h_max = shannon_entropy([0.5, 0.5], normalized=True)
    assert pytest.approx(h_max) == 1.0

    # deterministic prediction should have entropy = 0.0
    h_zero = shannon_entropy([1.0, 0.0], normalized=True)
    assert pytest.approx(h_zero) == 0.0

    # 4 classes uniform: [0.25, 0.25, 0.25, 0.25]
    h_uni4 = shannon_entropy([0.25, 0.25, 0.25, 0.25], normalized=True)
    assert pytest.approx(h_uni4) == 1.0


def test_isotonic_calibrator_small_sample_platt():
    # Small sample (<20) falls back to Platt scaling
    scores = [0.1, 0.2, 0.8, 0.9, 0.3, 0.7]
    targets = [0, 0, 1, 1, 0, 1]
    calibrator = IsotonicCalibrator(min_samples_isotonic=20)
    calibrator.fit(scores, targets)
    assert calibrator.method == "platt"
    assert calibrator.calibrate(0.85) > calibrator.calibrate(0.15)


def test_isotonic_calibrator_large_sample():
    # Large sample (>=20) uses isotonic regression
    scores = np.linspace(0.1, 0.9, 25)
    targets = (scores > 0.5).astype(int)
    calibrator = IsotonicCalibrator(min_samples_isotonic=20)
    calibrator.fit(scores, targets)
    assert calibrator.method == "isotonic"
    probas = calibrator.predict_proba([0.2, 0.8])
    assert probas[0] < probas[1]


def test_prediction_result_with_calibrated_probabilities():
    res = PredictionResult(
        labels=[1],
        confidence=[0.45],
        abstain=True,
        key=("wheat", "khuzestan"),
        n_samples=1,
        model_version="v1",
        calibrated_probabilities=[[0.55, 0.45]],
        abstain_reason="low_confidence: 0.45 < 0.6",
    )
    assert res.abstain is True
    assert res.calibrated_probabilities == [[0.55, 0.45]]
    assert "low_confidence" in res.abstain_reason


def test_compute_final_confidence():
    # When entropy is 0, score is 0.7 * proba + 0.3
    res = compute_final_confidence(1.0, 0.0)
    assert pytest.approx(res) == 1.0

    # Low calibrated proba, high entropy
    res2 = compute_final_confidence(0.5, 1.0)
    assert res2 < 0.5


def test_calibration_curve_insufficient_data():
    cc = CalibrationCurve()
    assert cc.calibrate(0.55) == 0.55


def test_calibration_curve_fit():
    cc = CalibrationCurve()
    for _ in range(10):
        cc.add_observation(0.55, 1)
    cal = cc.calibrate(0.55)
    assert cal > 0.55  # upward adjustment


def test_entropy_based_abstention():
    # proba = [0.4, 0.35, 0.25] -> entropy > 0.8 bits
    cm = ConfidenceModel(threshold=0.6, entropy_threshold=0.8)
    _confidences, abstain = cm.evaluate([[0.4, 0.35, 0.25]])
    assert abstain is True


def test_isotonic_calibrator_predict_proba_and_edge_cases():
    # Re-export coverage
    import geolearn.adapter
    import geolearn.scheduler

    assert geolearn.adapter is not None
    assert geolearn.scheduler is not None

    cal = IsotonicCalibrator()

    # Empty array before fit (identity)
    assert len(cal.predict_proba([])) == 0
    assert cal.calibrate(0.4) == 0.4

    # Mismatched lengths
    with pytest.raises(ValueError, match="same length"):
        cal.fit([0.1, 0.2], [0])

    # Empty fit
    empty_cal = IsotonicCalibrator().fit([], [])
    assert empty_cal.method == "identity"

    # Constant target fit (single class)
    const_cal = IsotonicCalibrator()
    const_cal.fit([0.2, 0.7, 0.9], [1, 1, 1])
    assert const_cal.method == "constant"
    assert const_cal.calibrate(0.5) == 1.0
    probas = const_cal.predict_proba([0.1, 0.5, 0.9])
    assert np.allclose(probas, [1.0, 1.0, 1.0])

    # Platt scaling predict_proba (< 20 samples)
    platt_cal = IsotonicCalibrator(min_samples_isotonic=20)
    platt_cal.fit([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
    assert platt_cal.method == "platt"
    platt_probas = platt_cal.predict_proba([0.15, 0.85])
    assert len(platt_probas) == 2
    assert platt_probas[0] < platt_probas[1]
    assert len(platt_cal.predict_proba([])) == 0

