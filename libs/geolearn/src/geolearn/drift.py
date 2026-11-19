"""Concept drift detection for online learning in GeoLearn."""

from __future__ import annotations

from math import isfinite
from numbers import Real
from typing import Any

from geolearn.online import DriftDetector, RiverDriftDetector, SimpleDriftDetector


class PageHinkley:
    """Page-Hinkley test for concept drift detection on streaming residuals/errors.

    Maintains running mean and cumulative sum of deviations:
    U_n = sum_{i=1}^n (x_i - mean_i - delta)
    m_n = min_{1<=i<=n} U_i
    PH_n = U_n - m_n
    Drift is flagged when n >= min_instances and PH_n > threshold.
    """

    def __init__(
        self,
        min_instances: int = 30,
        delta: float = 0.005,
        threshold: float = 50.0,
        alpha: float = 1.0,
    ) -> None:
        self.min_instances = int(min_instances)
        self.delta = float(delta)
        self.threshold = float(threshold)
        self.alpha = float(alpha)
        self.reset()

    def reset(self) -> None:
        self.n_instances: int = 0
        self.mean: float = 0.0
        self.sum_val: float = 0.0
        self.min_sum: float = 0.0
        self.drift_detected: bool = False
        self.ph_value: float = 0.0

    def update(self, value: float) -> bool:
        """Update test with a new scalar observation (e.g. error residual).

        Returns:
            True if drift was detected on this observation, False otherwise.
        """
        x = float(value)
        if not isfinite(x):
            raise ValueError("Residual must be finite")
        self.n_instances += 1
        # Running mean
        self.mean += (x - self.mean) / self.n_instances
        # Cumulative deviation
        self.sum_val = self.alpha * self.sum_val + (x - self.mean - self.delta)
        self.min_sum = min(self.min_sum, self.sum_val)

        self.ph_value = self.sum_val - self.min_sum
        if self.n_instances >= self.min_instances and self.ph_value > self.threshold:
            self.drift_detected = True
            # Reset cumulative statistics on drift detection
            self.n_instances = 0
            self.mean = x
            self.sum_val = 0.0
            self.min_sum = 0.0
        else:
            self.drift_detected = False

        return self.drift_detected

    def check(self, y_pred: Any, y_true: Any = None) -> bool:
        """Protocol compatibility with DriftDetector."""
        if y_true is None and isinstance(y_pred, Real):
            val = float(y_pred)
        else:
            val = 1.0 if y_pred != y_true else 0.0
        return self.update(val)


__all__ = ["DriftDetector", "PageHinkley", "RiverDriftDetector", "SimpleDriftDetector"]
