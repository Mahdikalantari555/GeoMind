"""Regression detection and CI-ready output for eval runs.

Core function :func:`detect_drift` compares baseline and current metric
maps, flagging any absolute delta exceeding a threshold.  The
:func:`to_ci_json` serializer produces a compact JSON diff report suitable
for CI pipeline consumption.
"""

from __future__ import annotations

import json
from typing import Any


def _is_grouped(metrics: dict[str, Any]) -> bool:
    return bool(metrics) and all(isinstance(v, dict) for v in metrics.values())


def detect_drift(
    baseline_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
    *,
    threshold: float = 0.05,
) -> dict[str, Any]:
    """Detect per-metric drift between two run metric maps.

    Accepts either flat metric maps (``{"recall@5": 0.7}``) or family-grouped
    maps (``{"retrieval": {"recall@5": 0.7}}``).  Returns a dict with the same
    shape as the inputs where each leaf is ``{baseline, current, delta,
    regressed}``.  ``regressed`` is ``True`` when ``abs(delta) > threshold``.
    """
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        raise ValueError(f"threshold must be numeric, got {type(threshold).__name__}")
    if threshold < 0:
        raise ValueError("threshold must be non-negative")

    if _is_grouped(baseline_metrics) or _is_grouped(current_metrics):
        result: dict[str, Any] = {}
        families = list(baseline_metrics.keys())
        for f in current_metrics:
            if f not in families:
                families.append(f)
        for family in families:
            base_vals = baseline_metrics.get(family, {})
            curr_vals = current_metrics.get(family, {})
            family_out: dict[str, Any] = {}
            for metric in base_vals:
                if metric in curr_vals:
                    family_out[metric] = _drift_entry(base_vals[metric], curr_vals[metric], threshold)
            for metric in curr_vals:
                if metric not in base_vals:
                    family_out[metric] = {
                        "baseline": None,
                        "current": float(curr_vals[metric]),
                        "delta": None,
                        "regressed": False,
                    }
            if family_out:
                result[family] = family_out
        return result

    result_flat: dict[str, Any] = {}
    for metric in baseline_metrics:
        if metric in current_metrics:
            result_flat[metric] = _drift_entry(
                baseline_metrics[metric], current_metrics[metric], threshold
            )
    return result_flat


def _drift_entry(base_val: Any, curr_val: Any, threshold: float) -> dict[str, Any]:
    delta = float(curr_val) - float(base_val)
    return {
        "baseline": float(base_val),
        "current": float(curr_val),
        "delta": round(delta, 6),
        "regressed": abs(delta) > threshold,
    }


def has_regression(drift: dict[str, Any]) -> bool:
    """Return True when any metric is flagged as regressed."""
    for value in drift.values():
        if isinstance(value, dict):
            if value.get("regressed") is True:
                return True
            if has_regression(value):
                return True
    return False


def _flatten_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Flatten family-grouped metrics into dotted keys."""
    flat: dict[str, Any] = {}
    if _is_grouped(metrics):
        for family, family_metrics in metrics.items():
            if isinstance(family_metrics, dict):
                for metric, entry in family_metrics.items():
                    flat[f"{family}.{metric}" if family else metric] = entry
    else:
        flat.update(metrics)
    return flat


def to_ci_json(
    diff_result: dict[str, Any],
    *,
    threshold: float = 0.05,
) -> dict[str, Any]:
    """Build a CI-compatible diff report from any diff-like *diff_result*.

    Accepts either a comparison diff from :func:`geomemory.eval.run_store`
    (with ``run_a``/``run_b``/``changed``/``query_diff``) or a pre-built report
    (with ``baseline_run``/``current_run``/``benchmarks``/``ok``).
    """
    baseline_run = diff_result.get("baseline_run", diff_result.get("run_a", ""))
    current_run = diff_result.get("current_run", diff_result.get("run_b", ""))
    dataset = diff_result.get("dataset", "")
    changed = diff_result.get("changed", False)
    query_diff = diff_result.get("query_diff", {})

    raw_benchmarks = diff_result.get("benchmarks")
    drifts: dict[str, Any] = {}
    benchmarks: list[dict[str, Any]] = []

    if isinstance(raw_benchmarks, list):
        for b in raw_benchmarks:
            if not isinstance(b, dict):
                continue
            bname = str(b.get("name", ""))
            b_metrics = b.get("metrics", {})
            b_queries = b.get("queries", [])
            drift = diff_result.get("drifts", {}).get(bname) if diff_result.get("drifts") else None
            if drift is None:
                drift = detect_drift(b_metrics.get("_baseline", {}), b_metrics.get("_current", {}), threshold=threshold)
            drifts[bname] = drift
            benchmarks.append({
                "name": bname,
                "metrics": _flatten_metrics(drift) if drift else {},
                "queries": b_queries,
            })
    elif isinstance(raw_benchmarks, dict):
        for bname, bdata in raw_benchmarks.items():
            metrics = bdata.get("metrics", {}) if isinstance(bdata, dict) else {}
            queries = bdata.get("queries", []) if isinstance(bdata, dict) else []
            benchmarks.append({
                "name": str(bname),
                "metrics": _flatten_metrics(metrics),
                "queries": queries,
            })
    elif diff_result.get("drifts"):
        for bname, drift in diff_result["drifts"].items():
            drifts[bname] = drift
            benchmarks.append({
                "name": str(bname),
                "metrics": _flatten_metrics(drift) if drift else {},
                "queries": [],
            })

    if not benchmarks and "metrics" in diff_result:
        benchmarks.append({
            "name": "",
            "metrics": _flatten_metrics(diff_result["metrics"]),
            "queries": [],
        })

    queries = [
        {"query": q, "delta_retrieved_add": v.get("new_in_b", []),
         "delta_retrieved_remove": v.get("missing_in_b", [])}
        for q, v in query_diff.items()
        if isinstance(v, dict) and (v.get("missing_in_b") or v.get("new_in_b"))
    ]
    if queries and benchmarks:
        benchmarks[-1]["queries"] = queries

    regression = has_regression(drifts) if drifts else False
    query_regression = changed and bool(query_diff)
    ok = bool(diff_result["ok"]) if "ok" in diff_result else not (regression or query_regression)

    return {
        "baseline_run": str(baseline_run),
        "current_run": str(current_run),
        "dataset": dataset,
        "benchmarks": benchmarks,
        "ok": ok,
        "threshold": float(threshold),
    }


def ci_json_to_string(diff: dict[str, Any]) -> str:
    """Serialize a CI diff report to compact JSON string."""
    return json.dumps(diff, sort_keys=True, indent=2, ensure_ascii=False)


__all__ = [
    "ci_json_to_string",
    "detect_drift",
    "has_regression",
    "to_ci_json",
]
