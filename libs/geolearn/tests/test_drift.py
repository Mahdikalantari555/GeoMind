"""Unit tests for PageHinkley drift detector and StreamingWindow."""

import numpy as np
from geolearn.classifier import OnlineClassifier
from geolearn.drift import PageHinkley, RiverDriftDetector, SimpleDriftDetector
from geolearn.streaming import StreamingWindow


def test_page_hinkley_no_drift_stationary() -> None:
    # Stationary series with mean ~ 0.05
    rng = np.random.default_rng(42)
    ph = PageHinkley(min_instances=30, delta=0.01, threshold=20.0)

    drift_count = 0
    for _ in range(100):
        val = rng.normal(0.05, 0.01)
        if ph.update(val):
            drift_count += 1

    assert drift_count == 0
    assert ph.drift_detected is False


def test_page_hinkley_drift_simulation() -> None:
    # Initial stationary period then strong upward shift
    rng = np.random.default_rng(123)
    ph = PageHinkley(min_instances=20, delta=0.005, threshold=15.0)

    # 40 normal observations
    for _ in range(40):
        ph.update(rng.normal(0.02, 0.01))

    # Shift distribution sharply to mean 1.5
    detected = False
    for _ in range(50):
        val = rng.normal(1.5, 0.1)
        if ph.update(val):
            detected = True
            break

    assert detected is True


def test_page_hinkley_check_protocol() -> None:
    ph = PageHinkley(min_instances=10, threshold=2.0)
    # Baseline phase with correct predictions
    for _ in range(15):
        ph.check(y_pred=0, y_true=0)
    # Shift phase with consecutive errors
    detected = False
    for _ in range(30):
        if ph.check(y_pred=1, y_true=0):
            detected = True
            break
    assert detected is True


def test_streaming_window_fifo_and_arrays() -> None:
    window = StreamingWindow(max_size=3)
    assert len(window) == 0
    assert not window.is_full

    window.add([1.0, 2.0], label=0)
    window.add([3.0, 4.0], label=1)
    window.add([5.0, 6.0], label=0)
    assert window.is_full
    assert len(window) == 3

    # Add 4th item, should evict 1st
    window.add([7.0, 8.0], label=1)
    assert len(window) == 3

    X, y = window.get_arrays()
    assert X.shape == (3, 2)
    assert y is not None
    assert np.array_equal(y, [1, 0, 1])
    assert np.allclose(X[0], [3.0, 4.0])


def test_streaming_window_update_classifier() -> None:
    window = StreamingWindow(max_size=10)
    clf = OnlineClassifier()
    # Fit initially
    clf.fit([[0.1, 0.2], [0.8, 0.9]], [0, 1])

    # Populate streaming window
    for _ in range(5):
        window.add([0.15, 0.25], label=0)
        window.add([0.85, 0.95], label=1)

    updated_count = window.update_classifier(clf, batch_size=4)
    assert updated_count == 10
    assert clf.n_samples_ >= 12


def test_river_drift_detector_fallback_and_present() -> None:
    # Test SimpleDriftDetector directly
    simple = SimpleDriftDetector(error_rate_threshold=0.2, window=10)
    assert simple.error_rate == 0.0
    for _ in range(5):
        simple.check(0, 0)
    assert simple.error_rate == 0.0
    assert not simple.detected

    # Add errors to exceed threshold
    for _ in range(5):
        simple.check(1, 0)
    assert simple.error_rate == 0.5
    assert simple.detected

    simple.reset()
    assert simple.error_rate == 0.0
    assert not simple.detected

    # Invalid window size
    import pytest

    with pytest.raises(ValueError, match="window must be positive"):
        SimpleDriftDetector(window=0)

    # RiverDriftDetector fallback mode (forced river absent)
    rdd_fallback = RiverDriftDetector(error_rate_threshold=0.3, window=10)
    rdd_fallback.using_river = False
    rdd_fallback._river_detector = None
    rdd_fallback._fallback = SimpleDriftDetector(error_rate_threshold=0.3, window=10)

    for _ in range(5):
        rdd_fallback.check(0, 0)
    assert not rdd_fallback.detected

    for _ in range(5):
        rdd_fallback.check(1, 0)
    assert rdd_fallback.detected
    rdd_fallback.reset()
    assert not rdd_fallback.detected

    # Mock river detector present
    class MockRiverDetector:
        def __init__(self) -> None:
            self.drift_detected = False
            self.updates = 0

        def update(self, val: float) -> None:
            self.updates += 1
            if val > 0.5:
                self.drift_detected = True

        def _reset(self) -> None:
            self.drift_detected = False
            self.updates = 0

    rdd_present = RiverDriftDetector()
    rdd_present.using_river = True
    rdd_present._river_detector = MockRiverDetector()
    rdd_present._fallback = None

    assert not rdd_present.check(0, 0)
    assert rdd_present.check(1, 0)
    assert rdd_present.detected
    rdd_present.reset()
    assert not rdd_present.detected


def test_streaming_window_edge_cases() -> None:
    import pytest

    # Invalid max_size
    with pytest.raises(ValueError, match="max_size must be positive"):
        StreamingWindow(max_size=0)

    win = StreamingWindow(max_size=5)
    # Empty window get_arrays
    X_empty, y_empty = win.get_arrays()
    assert X_empty.shape == (0, 0)
    assert y_empty is None

    # Unlabeled data
    win.add([1.0, 2.0])
    win.append([3.0, 4.0])
    X_unlabeled, y_unlabeled = win.get_arrays()
    assert X_unlabeled.shape == (2, 2)
    assert y_unlabeled is None

    # Iteration and clear
    assert len(list(iter(win))) == 2
    win.clear()
    assert len(win) == 0

