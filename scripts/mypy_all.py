#!/usr/bin/env python3
"""Run ``mypy --strict`` for every Python project and print combined output.

Each project owns its own pyproject.toml (strict=true, per-project error-code
disable list), so mypy must run from each project directory. This wrapper makes
that a single cross-platform command whose output is stable between developer
machines and CI, for use with ``scripts/check_baseline.py``.

Every diagnostic line is prefixed with its project path so diagnostics from
different projects cannot collide when the baseline normalises line numbers.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (project directory, source directory relative to it)
PROJECTS = [
    ("libs/geodomain", "src/"),
    ("libs/geospatial_core", "src/"),
    ("libs/data_engine", "src/"),
    ("libs/geoagent", "src/"),
    ("libs/geomemory", "src/"),
    ("libs/geolearn", "src/"),
    ("server", "src/"),
]


def main() -> int:
    for project, source in PROJECTS:
        process = subprocess.run(
            [sys.executable, "-m", "mypy", "--strict", source],
            cwd=ROOT / project,
            capture_output=True,
            text=True,
            check=False,
        )
        output = process.stdout + process.stderr
        for line in output.splitlines():
            if not line.strip():
                continue
            # Skip mypy's per-run summary; only diagnostics go into the baseline.
            if line.startswith(("Success:", "Found ")):
                continue
            print(f"{project}/{line}")
    # Always exit 0: check_baseline.py — not mypy — decides pass/fail against
    # the baseline, so pre-existing diagnostics do not fail the gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
