"""Layering audit: geolearn must not import geomemory or read its storage.

ARCHITECTURE.md deviation #2 (geolearn reading geomemory.db via raw SQLite)
was resolved by the CandidateMemoryProvider port. These tests keep it
resolved — a regression here is a build failure, not a docs note.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
from geolearn.ports import CandidateMemoryProvider
from geolearn.training_pipeline import TrainingPipeline

_SRC = Path(__file__).resolve().parents[1] / "src" / "geolearn"


def test_geolearn_src_never_imports_geomemory() -> None:
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "geomemory" or alias.name.startswith("geomemory."):
                        offenders.append(f"{py.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and (
                node.module == "geomemory" or (node.module or "").startswith("geomemory.")
            ):
                offenders.append(f"{py.name}: from {node.module}")
    assert offenders == [], f"geolearn imports geomemory: {offenders}"


def test_geolearn_src_has_no_raw_sql_on_foreign_dbs() -> None:
    """No module may open a `geomemory.db` / `workspace.db` path directly."""
    offenders: list[str] = []
    for py in _SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "geomemory.db" in text or "workspace.db" in text:
            offenders.append(py.name)
    assert offenders == [], f"geolearn references foreign DB filenames: {offenders}"


class _InMemoryProvider:
    def __init__(self, items: list[dict[str, str]]) -> None:
        self._items = items

    def list_candidate_memories(
        self, states: list[str] | None = None, **kwargs: object
    ) -> list[object]:
        return [
            type("C", (), {"id": it["id"], "content": it["content"]})()
            for it in self._items
        ]


def test_provider_protocol_is_structural() -> None:
    provider = _InMemoryProvider([])
    assert isinstance(provider, CandidateMemoryProvider)


def test_provider_errors_are_isolated(tmp_path: Path) -> None:
    class _BrokenProvider:
        def list_candidate_memories(
            self, states: list[str] | None = None, **kwargs: object
        ) -> list[object]:
            raise RuntimeError("upstream gone")

    pipeline = TrainingPipeline(tmp_path, candidate_source=_BrokenProvider())  # type: ignore[arg-type]
    assert pipeline.pending_count() == {"total_pending": 0, "by_key": {}}
    assert pipeline.train_on_feedback() == {}


def test_training_with_injected_provider(tmp_path: Path) -> None:
    pipeline = TrainingPipeline(tmp_path / "geolearn", candidate_source=_InMemoryProvider([]))
    pipeline.cache.insert("asset-1", np.ones(4, dtype=np.float32))
    pipeline.cache.insert("asset-2", -np.ones(4, dtype=np.float32))
    pipeline.candidate_source = _InMemoryProvider([
        {"id": "fb-1", "content": '{"asset_id": "asset-1", "label": 1, "crop_type": "sugarcane", "region": "khuzestan"}'},
        {"id": "fb-2", "content": '{"asset_id": "asset-2", "label": 0, "crop_type": "sugarcane", "region": "khuzestan"}'},
    ])
    result = pipeline.train_on_feedback()
    assert result["sugarcane__khuzestan"]["samples_trained"] == 2
