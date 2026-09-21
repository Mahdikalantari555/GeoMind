"""Tests for geomemory.eval.regression."""

from __future__ import annotations

import json
import pytest

from geomemory.eval.regression import detect_drift, has_regression, to_ci_json


class TestDetectDrift:
    def test_within_threshold(self):
        base = {"retrieval": {"recall@5": 0.70}}
        curr = {"retrieval": {"recall@5": 0.73}}
        drift = detect_drift(base, curr, threshold=0.05)
        assert drift["retrieval"]["recall@5"]["delta"] == pytest.approx(0.03)
        assert not drift["retrieval"]["recall@5"]["regressed"]

    def test_exceeded_threshold(self):
        base = {"retrieval": {"recall@5": 0.70}}
        curr = {"retrieval": {"recall@5": 0.63}}
        drift = detect_drift(base, curr, threshold=0.05)
        assert drift["retrieval"]["recall@5"]["delta"] == pytest.approx(-0.07)
        assert drift["retrieval"]["recall@5"]["regressed"]

    def test_exact_equality(self):
        base = {"retrieval": {"recall@5": 0.50}}
        curr = {"retrieval": {"recall@5": 0.50}}
        drift = detect_drift(base, curr, threshold=0.05)
        assert drift["retrieval"]["recall@5"]["delta"] == 0.0
        assert not drift["retrieval"]["recall@5"]["regressed"]

    def test_current_only_family(self):
        base = {}
        curr = {"qa": {"abstain_rate": 0.3}}
        drift = detect_drift(base, curr)
        assert "qa" in drift
        assert drift["qa"]["abstain_rate"]["current"] == 0.3

    def test_default_threshold(self):
        base = {"retrieval": {"recall@5": 0.60}}
        curr = {"retrieval": {"recall@5": 0.64}}
        drift = detect_drift(base, curr)
        assert not drift["retrieval"]["recall@5"]["regressed"]

    def test_multi_metrics(self):
        base = {"retrieval": {"recall@5": 0.6, "precision@5": 0.8}}
        curr = {"retrieval": {"recall@5": 0.5, "precision@5": 0.8}}
        drift = detect_drift(base, curr, threshold=0.05)
        assert drift["retrieval"]["recall@5"]["regressed"]
        assert not drift["retrieval"]["precision@5"]["regressed"]


class TestHasRegression:
    def test_true_when_regressed(self):
        drift = {"retrieval": {"recall@5": {"regressed": True}}}
        assert has_regression(drift) is True

    def test_false_when_all_clear(self):
        drift = {"retrieval": {"recall@5": {"regressed": False}}}
        assert has_regression(drift) is False


class TestToCiJson:
    def test_round_trip(self):
        drifts = {
            "b1": {
                "retrieval": {
                    "recall@5": {
                        "baseline": 0.7,
                        "current": 0.6,
                        "delta": -0.1,
                        "regressed": True,
                    }
                }
            }
        }
        out = to_ci_json(
            {
                "baseline_run": "/a/run1",
                "current_run": "/a/run2",
                "dataset": "test_ds",
                "benchmarks": [{"name": "b1", "metrics": {}}],
                "drifts": drifts,
            },
            threshold=0.05,
        )
        assert out["ok"] is False
        assert out["dataset"] == "test_ds"
        assert len(out["benchmarks"]) == 1
        assert out["benchmarks"][0]["name"] == "b1"

    def test_ok_when_no_regression(self):
        drifts: dict = {}
        out = to_ci_json(
            {
                "baseline_run": "/a",
                "current_run": "/b",
                "dataset": "ds",
                "benchmarks": [],
                "drifts": drifts,
            }
        )
        assert out["ok"] is True
