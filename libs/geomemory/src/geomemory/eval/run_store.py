"""Run artifact persistence for the eval framework.

Layout: ``geomemory-evals/runs/<dataset>/<timestamp>/`` with a ``stats.json``
plus one ``<benchmark>.json`` per benchmark. Artifacts are immutable: a second
run always writes a new directory, never mutating the first.

Baseline storage: ``geomemory-evals/baselines/<dataset>.json`` containing a
single object with ``timestamp``, ``path``, and ``metrics`` keys.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any

from geomemory.eval.pipeline_stats import STATS_FIELDS


def _utcnow_stamp() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sanitize_timestamp(timestamp: str | None) -> str:
    """Normalize a timestamp to a filesystem-safe, sortable string."""
    if not timestamp:
        return _utcnow_stamp()
    cleaned = re.sub(r"[^A-Za-z0-9T:\-_.]", "", timestamp)
    return cleaned or _utcnow_stamp()


def _sanitize_dataset(dataset: str) -> str:
    """Reject dataset names that could escape their eval subdirectory."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", dataset)
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError(f"Invalid dataset name: {dataset!r}")
    return cleaned


def _unique_run_dir(base: Path, dataset: str, timestamp: str) -> Path:
    """Return a run directory that does not yet exist, retrying on collisions."""
    candidate = base / dataset / timestamp
    if not candidate.exists():
        return candidate
    # Same-second collision: append a monotonic suffix until unique.
    index = 1
    while True:
        suffixed = f"{timestamp}-{index}"
        candidate = base / dataset / suffixed
        if not candidate.exists():
            return candidate
        index += 1


class RunStore:
    """Persist and read eval run artifacts under a base directory."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ── Writing ────────────────────────────────────────────────────────────

    def write_run(
        self,
        dataset: str,
        benchmark: str,
        stats: dict[str, Any],
        rows: list[dict[str, Any]],
        *,
        timestamp: str | None = None,
        config: dict[str, Any] | None = None,
        name: str | None = None,
        metrics: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> Path:
        """Write a complete run directory. Returns the run directory path.

        ``stats`` must satisfy the pipeline-stats schema (all eight numeric
        fields). ``rows`` is the per-query artifact list. Writes are atomic
        within the run directory: a partial write never overwrites a prior
        run, because each invocation targets a fresh directory.
        """
        stamp = _sanitize_timestamp(timestamp)
        run_dir = _unique_run_dir(self.base_dir, dataset, stamp)
        run_dir.mkdir(parents=True, exist_ok=True)

        stats_path = run_dir / "stats.json"
        stats_path.write_text(_dumps(stats), encoding="utf-8")

        benchmark_name = name or benchmark
        result_path = run_dir / f"{benchmark}.json"
        result_path.write_text(
            _dumps(
                {
                    "name": benchmark_name,
                    "config": config or {},
                    "metrics": metrics or {},
                    "rows": rows,
                    "manifest": manifest,
                }
            ),
            encoding="utf-8",
        )
        return run_dir

    def write_stats_only(
        self,
        dataset: str,
        stats: dict[str, Any],
        *,
        timestamp: str | None = None,
    ) -> Path:
        """Write only ``stats.json`` (used by `eval rebuild` / `eval stats`)."""
        stamp = _sanitize_timestamp(timestamp)
        run_dir = _unique_run_dir(self.base_dir, dataset, stamp)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "stats.json").write_text(_dumps(stats), encoding="utf-8")
        return run_dir

    # ── Reading ─────────────────────────────────────────────────────────────

    def read_run(self, dataset: str, timestamp: str) -> dict[str, Any]:
        """Read a run directory's artifacts into a dict.

        Returns ``{stats, benchmarks: {name: {...}}, manifest}``. Raises
        ``FileNotFoundError`` when the run directory does not exist.
        """
        run_dir = self.base_dir / dataset / _sanitize_timestamp(timestamp)
        if not run_dir.is_dir():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        stats = _load(run_dir / "stats.json")
        benchmarks: dict[str, Any] = {}
        for path in sorted(run_dir.glob("*.json")):
            if path.name == "stats.json":
                continue
            benchmarks[path.stem] = _load(path)
        manifest = _load(run_dir / "manifest.json") if (run_dir / "manifest.json").is_file() else None
        return {
            "dataset": dataset,
            "timestamp": timestamp,
            "path": str(run_dir),
            "stats": stats,
            "benchmarks": benchmarks,
            "manifest": manifest,
        }

    def list_runs(self, dataset: str | None = None) -> list[dict[str, Any]]:
        """List run directories under the store, newest first."""
        results: list[dict[str, Any]] = []
        if dataset is not None:
            datasets = [self.base_dir / dataset] if (self.base_dir / dataset).is_dir() else []
        else:
            datasets = sorted(p for p in self.base_dir.iterdir() if p.is_dir())
        for ds_dir in datasets:
            for run_dir in sorted(ds_dir.iterdir(), reverse=True):
                if not run_dir.is_dir():
                    continue
                stats_path = run_dir / "stats.json"
                if not stats_path.is_file():
                    continue
                results.append(
                    {
                        "dataset": ds_dir.name,
                        "timestamp": run_dir.name,
                        "path": str(run_dir),
                        "stats": _load(stats_path),
                    }
                )
        return results


class BaselineStore:
    """Persist and inspect baseline pins per dataset.

    Baselines live at ``geomemory-evals/baselines/<dataset>.json`` with schema::

        {
          "timestamp": "<ISO-ish stamp>",
          "path": "<absolute run dir path>",
          "metrics": {"retrieval": {...}, "qa": {...}}
        }
    """

    def __init__(self, baselines_dir: str | Path) -> None:
        self.baselines_dir = Path(baselines_dir)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def set(self, dataset: str, timestamp: str, path: str | Path, metrics: dict[str, Any]) -> None:
        """Pin *dataset*'s baseline to the run at *path* with *timestamp*."""
        data = {
            "timestamp": timestamp,
            "path": str(path),
            "metrics": metrics,
        }
        out_path = self.baselines_dir / f"{dataset}.json"
        out_path.write_text(_dumps(data), encoding="utf-8")

    def get(self, dataset: str) -> dict[str, Any] | None:
        """Return the baseline for *dataset*, or ``None`` if unset."""
        baseline_path = self.baselines_dir / f"{dataset}.json"
        if not baseline_path.is_file():
            return None
        return _load(baseline_path)

    def list_datasets(self) -> list[dict[str, Any]]:
        """Return all pinned baselines as ``[{dataset, timestamp, path}]``."""
        results: list[dict[str, Any]] = []
        if not self.baselines_dir.is_dir():
            return results
        for p in sorted(self.baselines_dir.glob("*.json")):
            if p.name == ".gitignore":
                continue
            data = _load(p)
            results.append({
                "dataset": p.stem,
                "timestamp": data.get("timestamp", ""),
                "path": data.get("path", ""),
                "metrics": data.get("metrics", {}),
            })
        return results


def _dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_stats(stats: Any) -> bool:
    """Return True when ``stats`` has all eight numeric fields."""
    if not isinstance(stats, dict):
        return False
    for field in STATS_FIELDS:
        if field not in stats:
            return False
        value = stats[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
    return True


__all__ = ["RunStore", "BaselineStore", "validate_stats"]
