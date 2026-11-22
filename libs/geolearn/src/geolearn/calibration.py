from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression


def prediction_entropy(proba_array: Any) -> float:
    """Compute prediction entropy -sum(p * log(p)) in natural units (nats).

    Retained for callers that need the raw value; decisions MUST use
    ``normalized_entropy`` so one scale is used everywhere (L-064).
    """
    arr = np.asarray(proba_array, dtype=np.float64)
    if arr.size <= 1:
        return 0.0
    arr = arr[arr > 0]
    if len(arr) == 0:
        return 0.0
    return float(-np.sum(arr * np.log(arr)))


def normalized_entropy(proba_array: Any) -> float:
    """Canonical Shannon entropy in bits, normalised to [0, 1].

    This is the single scale used for abstention and confidence blending,
    matching ``geolearn.confidence.shannon_entropy(..., normalized=True)``.
    """
    arr = np.asarray(proba_array, dtype=np.float64).ravel()
    arr = arr[arr > 0]
    if arr.size <= 1:
        return 0.0
    total = float(arr.sum())
    if total <= 0:
        return 0.0
    probs = arr / total
    ent = float(-np.sum(probs * np.log2(probs)))
    max_ent = math.log2(probs.size)
    return float(np.clip(ent / max_ent, 0.0, 1.0)) if max_ent > 0 else 0.0


def compute_final_confidence(calibrated_proba: float, entropy: float) -> float:
    """Blend calibrated probability with an already-normalised [0, 1] entropy."""
    entropy_norm = min(max(float(entropy), 0.0), 1.0)
    final = 0.7 * float(calibrated_proba) + 0.3 * (1.0 - entropy_norm)
    return float(np.clip(final, 0.0, 1.0))


class IsotonicCalibrator:
    """Isotonic probability calibration with Platt scaling fallback for small samples (<20)."""

    def __init__(self, min_samples_isotonic: int = 20, out_of_bounds: str = "clip") -> None:
        self.min_samples_isotonic = int(min_samples_isotonic)
        self.out_of_bounds = out_of_bounds
        self.model: Any = None
        self.method: str = "identity"

    def fit(
        self,
        scores: Sequence[float] | np.ndarray,
        targets: Sequence[int] | np.ndarray,
    ) -> IsotonicCalibrator:
        X = np.asarray(scores, dtype=np.float64).ravel()
        y = np.asarray(targets, dtype=np.float64).ravel()
        if len(X) != len(y):
            raise ValueError(f"scores and targets must have same length, got {len(X)} and {len(y)}")
        if len(X) == 0:
            self.model, self.method = None, "identity"
            return self
        if not np.isin(y, [0, 1]).all():
            raise ValueError("Calibration targets must be binary")

        unique_y = np.unique(y)
        if len(unique_y) <= 1:
            self.method = "constant"
            self.model = float(unique_y[0]) if len(unique_y) == 1 else 0.5
            return self

        if len(X) >= self.min_samples_isotonic:
            self.method = "isotonic"
            iso = IsotonicRegression(out_of_bounds=self.out_of_bounds, y_min=0.0, y_max=1.0)
            iso.fit(X, y)
            self.model = iso
        else:
            self.method = "platt"
            from sklearn.linear_model import LogisticRegression

            lr = LogisticRegression(C=1.0, solver="lbfgs")
            lr.fit(X.reshape(-1, 1), y.astype(int))
            self.model = lr
        return self

    def calibrate(self, score: float) -> float:
        if self.model is None or self.method == "identity":
            return float(np.clip(score, 0.0, 1.0))
        if self.method == "constant":
            return float(self.model)
        if self.method == "isotonic":
            pred = self.model.predict([float(score)])[0]
            return float(np.clip(pred, 0.0, 1.0))
        if self.method == "platt":
            proba = self.model.predict_proba([[float(score)]])[0, 1]
            return float(np.clip(proba, 0.0, 1.0))
        return float(np.clip(score, 0.0, 1.0))

    def predict_proba(self, scores: Sequence[float] | np.ndarray) -> np.ndarray:
        X = np.asarray(scores, dtype=np.float64).ravel()
        if len(X) == 0:
            return np.empty(0, dtype=np.float64)
        if self.model is None or self.method == "identity":
            return np.clip(X, 0.0, 1.0)
        if self.method == "constant":
            return np.full_like(X, float(self.model))
        if self.method == "isotonic":
            preds = np.asarray(self.model.predict(X), dtype=np.float64)
            return np.clip(preds, 0.0, 1.0)
        if self.method == "platt":
            probas = np.asarray(
                self.model.predict_proba(X.reshape(-1, 1))[:, 1], dtype=np.float64
            )
            return np.clip(probas, 0.0, 1.0)
        return np.clip(X, 0.0, 1.0)


class CalibrationCurve:
    def __init__(self, window_size: int = 100) -> None:
        self.window_size = window_size
        self.buffer: deque[tuple[float, int]] = deque(maxlen=window_size)
        self.calibrator = IsotonicCalibrator()

    def add_observation(self, predicted_proba: float, is_correct: int | bool) -> None:
        self.buffer.append((float(predicted_proba), int(is_correct)))
        if len(self.buffer) >= 10:
            self.fit()

    def fit(self) -> CalibrationCurve:
        if len(self.buffer) < 10:
            return self
        X = [x[0] for x in self.buffer]
        y = [x[1] for x in self.buffer]
        self.calibrator.fit(X, y)
        return self

    def calibrate(self, proba: float) -> float:
        if len(self.buffer) < 10:
            return float(proba)
        return self.calibrator.calibrate(proba)
