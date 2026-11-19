"""Counterexamples from the third QA pass; CPU only."""
from unittest.mock import Mock

import numpy as np
import pytest
from geolearn.calibration import IsotonicCalibrator
from geolearn.confidence import ConfidenceModel, shannon_entropy
from geolearn.drift import PageHinkley
from geolearn.online import OnlineScheduler
from geolearn.streaming import StreamingWindow


def test_entropy_in_bits():
    assert shannon_entropy([1, 1, 1, 1], normalized=False) == 2


def test_confidence_uses_normalized_entropy_once():
    row = [0.9, 0.1]
    assert ConfidenceModel().evaluate(row).confidences == pytest.approx([.7*.9 + .3*(1-shannon_entropy(row))])


def test_supplied_calibrator_used():
    cal = IsotonicCalibrator().fit([.1, .8], [0, 0])
    assert ConfidenceModel(calibration_curve=cal).evaluate([.9,.1]).calibrated_probabilities[0][0] == 0


def test_zero_mass_abstains_even_at_zero_threshold():
    assert ConfidenceModel(threshold=0).evaluate([0, 0]).abstain


def test_nan_cannot_produce_accepted_prediction():
    with pytest.raises(ValueError):
        ConfidenceModel().evaluate([np.nan, .5])


def test_constant_invalid_label_not_a_probability():
    with pytest.raises(ValueError):
        IsotonicCalibrator().fit([.4], [2])


def test_empty_refit_discards_old_model():
    cal=IsotonicCalibrator().fit([.4],[1]).fit([],[])
    assert cal.calibrate(.4)==.4


def test_invalid_drift_sample_does_not_poison_history():
    detector=PageHinkley()
    with pytest.raises(ValueError):
        detector.update(np.nan)
    assert detector.n_instances == 0


def test_numpy_residual_keeps_its_magnitude():
    detector=PageHinkley(); detector.check(np.float32(.25)); assert detector.mean==.25


def test_negative_batch_does_not_claim_training():
    w=StreamingWindow();w.add([1],1)
    with pytest.raises(ValueError): w.update_classifier(Mock(),batch_size=-1)


def test_mutating_input_does_not_relabel_historical_embedding():
    w=StreamingWindow(); x=np.array([1],dtype=np.float32); w.add(x,1); x[0]=9
    assert w.get_arrays()[0][0,0]==1


def test_scheduler_clock_can_start_at_zero():
    s=OnlineScheduler(min_interval_s=5); clf=Mock();s.maybe_train(clf,new_samples=[([1],1)],current_time=0)
    assert s.maybe_train(clf,current_time=5)


def test_force_includes_new_samples():
    s=OnlineScheduler(); s.add([1],0); clf=Mock(); assert s.step(clf,new_samples=[([2],1)],force=True)
    assert clf.partial_fit.call_args.args[1].tolist()==[0,1]
