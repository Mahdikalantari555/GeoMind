from __future__ import annotations

from typing import Any

import numpy as np

from geolearn.calibration import (
    CalibrationCurve,
    IsotonicCalibrator,
    compute_final_confidence,
    normalized_entropy,
    prediction_entropy,
)


def shannon_entropy(probabilities: Any, normalized: bool = True) -> float | np.ndarray:
    """Compute Shannon entropy across class distributions."""
    arr = np.asarray(probabilities, dtype=np.float64)
    is_1d = arr.ndim == 1
    if is_1d:
        arr = arr.reshape(1, -1)

    n_classes = arr.shape[1]
    if n_classes <= 1:
        return 0.0

    # One canonical entropy implementation/scale (L-064). For the multi-row
    # case keep the vectorised path below; its result is identical.
    if is_1d and normalized:
        return normalized_entropy(arr[0])

    row_sums = np.sum(arr, axis=1, keepdims=True)
    probs = np.divide(arr, row_sums, out=np.zeros_like(arr), where=row_sums > 0)

    safe_probs = np.where(probs > 0, probs, 1.0)
    log_probs = np.log2(safe_probs)
    entropy = -np.sum(np.where(probs > 0, probs * log_probs, 0.0), axis=1)

    if normalized and n_classes > 1:
        entropy = entropy / np.log2(float(n_classes))

    if normalized:
        entropy = np.clip(entropy, 0.0, 1.0)
    return float(entropy[0]) if is_1d else entropy


class ConfidenceEvaluation:
    """Container for confidence evaluation results supporting 2-tuple unpacking."""

    def __init__(
        self,
        confidences: list[float],
        abstain: bool,
        abstain_reason: str | None = None,
        calibrated_probabilities: list[list[float]] | None = None,
    ) -> None:
        self.confidences = confidences
        self.abstain = abstain
        self.abstain_reason = abstain_reason
        self.calibrated_probabilities = calibrated_probabilities

    def __iter__(self) -> Any:
        yield self.confidences
        yield self.abstain

    def __getitem__(self, idx: int) -> Any:
        return [self.confidences, self.abstain][idx]


class ConfidenceModel:
    def __init__(
        self,
        threshold: float = 0.6,
        entropy_threshold: float = 0.8,
        calibration_curve: CalibrationCurve | IsotonicCalibrator | None = None,
    ) -> None:
        self.threshold = float(threshold)
        self.entropy_threshold = float(entropy_threshold)
        self.calibration_curve = calibration_curve or CalibrationCurve()

    def evaluate(self, probabilities: Any) -> ConfidenceEvaluation:
        prob_arr = np.asarray(probabilities, dtype=np.float64)
        if prob_arr.ndim == 1:
            prob_arr = prob_arr.reshape(1, -1)

        confidences: list[float] = []
        cal_probas: list[list[float]] = []
        reasons: list[str] = []
        force_abstain = False

        if prob_arr.ndim != 2 or not prob_arr.shape[1] or not np.all(np.isfinite(prob_arr)) or np.any(prob_arr < 0):
            raise ValueError("Expected finite, non-negative class probabilities")
        for row in prob_arr:
            if not row.any():
                confidences.append(0.0)
                cal_probas.append(row.tolist())
                reasons.append("empty_probability_mass")
                force_abstain = True
                continue
            raw_max = float(np.max(row))
            cal_max = self.calibration_curve.calibrate(raw_max)
            if raw_max > 0:
                max_idx = int(np.argmax(row))
                cal_row = np.zeros_like(row)
                cal_row[max_idx] = cal_max
                other_sum = float(np.sum(row)) - raw_max
                if other_sum > 0:
                    for i in range(len(row)):
                        if i != max_idx:
                            cal_row[i] = (row[i] / other_sum) * (1.0 - cal_max)
                elif len(row) > 1:
                    fill = (1.0 - cal_max) / (len(row) - 1)
                    for i in range(len(row)):
                        if i != max_idx:
                            cal_row[i] = fill
            else:
                cal_row = row
            cal_probas.append([float(x) for x in cal_row])

            ent = float(shannon_entropy(row, normalized=True))
            final_conf = 0.7 * cal_max + 0.3 * (1.0 - ent)
            confidences.append(final_conf)

            if ent > self.entropy_threshold:
                force_abstain = True
                reasons.append(
                    f"high_entropy_uncertainty: entropy {ent:.3f} > {self.entropy_threshold:.3f}"
                )
            elif final_conf < self.threshold:
                reasons.append(f"low_confidence: {final_conf:.3f} < {self.threshold:.3f}")

        abstain = force_abstain or any(c < self.threshold for c in confidences)
        reason_str = "; ".join(reasons) if reasons else None
        return ConfidenceEvaluation(
            confidences=confidences,
            abstain=abstain,
            abstain_reason=reason_str,
            calibrated_probabilities=cal_probas,
        )

    def is_abstain(self, confidence: float) -> bool:
        return confidence < self.threshold


__all__ = [
    "ConfidenceEvaluation",
    "ConfidenceModel",
    "compute_final_confidence",
    "normalized_entropy",
    "prediction_entropy",
    "shannon_entropy",
]
