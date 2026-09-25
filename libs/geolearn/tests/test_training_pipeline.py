from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
from geolearn.cache import EmbeddingCache
from geolearn.training_pipeline import TrainingPipeline


def test_pipeline_training(tmp_path: Path) -> None:
    geolearn_dir = tmp_path / "geolearn"
    geomemory_dir = tmp_path / "geomemory"
    geolearn_dir.mkdir()
    geomemory_dir.mkdir()

    with sqlite3.connect(geomemory_dir / "geomemory.db") as conn:
        conn.execute(
            """
            CREATE TABLE candidate_memory (
                id TEXT PRIMARY KEY,
                content TEXT,
                state TEXT
            )
            """
        )
        conn.commit()

    cache = EmbeddingCache(geolearn_dir)
    cache.insert("a1", np.ones(8, dtype=np.float32))
    cache.insert("a2", -np.ones(8, dtype=np.float32))

    with sqlite3.connect(geomemory_dir / "geomemory.db") as conn:
        conn.execute(
            "INSERT INTO candidate_memory VALUES (?, ?, ?)",
            ("c1", json.dumps({"asset_id": "a1", "label": 1, "crop_type": "wheat", "region": "khuzestan"}), "verified"),
        )
        conn.execute(
            "INSERT INTO candidate_memory VALUES (?, ?, ?)",
            ("c2", json.dumps({"asset_id": "a2", "label": 0, "crop_type": "wheat", "region": "khuzestan"}), "supported"),
        )
        conn.execute(
            "INSERT INTO candidate_memory VALUES (?, ?, ?)",
            ("c3", json.dumps({"asset_id": "a3", "label": 1}), "proposed"),
        )
        conn.commit()

    pipeline = TrainingPipeline(geolearn_dir, geomemory_dir)
    p = pipeline.pending_count()
    assert p["total_pending"] == 2
    assert p["by_key"]["wheat__khuzestan"] == 2

    res = pipeline.train_on_feedback()
    assert "wheat__khuzestan" in res
    assert res["wheat__khuzestan"]["samples_trained"] == 2
    assert res["wheat__khuzestan"]["total_n_samples"] == 2

    p2 = pipeline.pending_count()
    assert p2["total_pending"] == 0


def test_pipeline_with_mock_facade(tmp_path: Path) -> None:
    from typing import Any

    geolearn_dir = tmp_path / "geolearn_facade"
    geolearn_dir.mkdir()

    class MockCandidate:
        def __init__(self, id: str, content: str, state: str) -> None:
            self.id = id
            self.content = content
            self.state = state

    class MockWorkspace:
        def __init__(self) -> None:
            self.queried_states: list[str] | None = None

        def list_candidate_memories(
            self, states: list[str] | None = None, **kwargs: Any
        ) -> list[MockCandidate]:
            self.queried_states = states
            return [
                MockCandidate(
                    "c1",
                    json.dumps(
                        {"asset_id": "a1", "label": 1, "crop_type": "barley", "region": "fars"}
                    ),
                    "verified",
                ),
                MockCandidate(
                    "c2",
                    json.dumps(
                        {"asset_id": "a2", "label": 0, "crop_type": "barley", "region": "fars"}
                    ),
                    "supported",
                ),
            ]

    ws = MockWorkspace()
    cache = EmbeddingCache(geolearn_dir)
    cache.insert("a1", np.ones(8, dtype=np.float32))
    cache.insert("a2", -np.ones(8, dtype=np.float32))

    pipeline = TrainingPipeline(geolearn_dir, ws)
    pending = pipeline.pending_count()
    assert pending["total_pending"] == 2
    assert pending["by_key"]["barley__fars"] == 2
    assert ws.queried_states == ["verified", "supported"]

    res = pipeline.train_on_feedback()
    assert "barley__fars" in res
    assert res["barley__fars"]["samples_trained"] == 2


def test_pipeline_rollback_on_revocation(tmp_path: Path) -> None:
    from typing import Any

    geolearn_dir = tmp_path / "geolearn_rollback"
    geolearn_dir.mkdir()

    class MockCandidate:
        def __init__(self, id: str, content: str, state: str) -> None:
            self.id = id
            self.content = content
            self.state = state

    class MockWorkspace:
        def __init__(self, c_list: list[MockCandidate]) -> None:
            self.candidates = c_list

        def list_candidate_memories(self, **kwargs: Any) -> list[MockCandidate]:
            return self.candidates

    cache = EmbeddingCache(geolearn_dir)
    cache.insert("a1", np.ones(8, dtype=np.float32))
    cache.insert("a2", -np.ones(8, dtype=np.float32))
    cache.insert("a3", np.full(8, 0.5, dtype=np.float32))

    batch1 = [
        MockCandidate(
            "fb_1",
            json.dumps({"asset_id": "a1", "label": 1, "crop_type": "rice", "region": "gilan"}),
            "verified",
        ),
        MockCandidate(
            "fb_2",
            json.dumps({"asset_id": "a2", "label": 0, "crop_type": "rice", "region": "gilan"}),
            "verified",
        ),
    ]
    ws = MockWorkspace(batch1)
    pipeline = TrainingPipeline(geolearn_dir, ws)

    # Train batch 1 -> Version 1
    res1 = pipeline.run()
    assert "rice__gilan" in res1
    assert res1["rice__gilan"]["samples_trained"] == 2
    versions1 = pipeline.store.list_versions(("rice", "gilan"))
    assert len(versions1) >= 1
    assert versions1[0].version == 1

    # Train batch 2 with erroneous feedback "fb_bad" -> Version 2
    batch2 = [
        MockCandidate(
            "fb_bad",
            json.dumps({"asset_id": "a3", "label": 1, "crop_type": "rice", "region": "gilan"}),
            "verified",
        ),
    ]
    ws.candidates = batch2
    res2 = pipeline.run()
    assert "rice__gilan" in res2
    versions2 = pipeline.store.list_versions(("rice", "gilan"))
    assert len(versions2) >= 2
    assert versions2[0].version == 2
    assert "fb_bad" in versions2[0].feedback_ids

    # Revoke "fb_bad" and trigger rollback
    rolled_back = pipeline.rollback_feedback("fb_bad", reason="User marked label incorrect")
    assert len(rolled_back) == 1
    key, target_v = rolled_back[0]
    assert key == ("rice", "gilan")
    assert target_v == 1
