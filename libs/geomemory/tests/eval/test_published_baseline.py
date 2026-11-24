"""Regression hook for the published agent baseline (ship-and-measure-agent).

Re-runs the frozen protocol and fails when the published retrieval numbers move
or when the citation-resolution invariant regresses below 1.0. This is the
machine-checked half of docs/benchmarks/report.md.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

# libs/geomemory/tests/eval/test_published_baseline.py → repo root
ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / "scripts" / "benchmark_agent_baseline.py"
RESULTS = ROOT / "docs" / "benchmarks" / "results.json"
TOLERANCE = 0.02


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_agent_baseline", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_published_results_exist() -> None:
    assert RESULTS.is_file(), f"missing published baseline: {RESULTS}"
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert set(data["retrieval"]) == {"hybrid", "sparse", "dense"}
    assert data["qa"]["oracle_stub"]["citation_resolution"] == 1.0


def test_published_baseline_is_reproducible(tmp_path: Path) -> None:
    published = json.loads(RESULTS.read_text(encoding="utf-8"))
    current = _load_script().run_benchmark(tmp_path)

    for mode, metrics in published["retrieval"].items():
        for key, expected in metrics.items():
            actual = current["retrieval"][mode][key]
            assert abs(actual - expected) <= TOLERANCE, (
                f"{mode}.{key}: published {expected:.3f}, rerun {actual:.3f}"
            )

    stub = current["qa"]["oracle_stub"]
    assert stub["citations_emitted"] > 0
    assert stub["citation_resolution"] == 1.0, (
        "every emitted citation must resolve to a real segment with a locator"
    )
