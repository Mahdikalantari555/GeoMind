from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from geolearn.cache import EmbeddingCache
from geolearn.training_pipeline import TrainingPipeline


class _StaticProvider:
    """Fake CandidateMemoryProvider with a mutable candidate list."""

    def __init__(self, candidates: list[tuple[str, str]]) -> None:
        self.candidates = candidates  # (id, content-json) tuples

    def list_candidate_memories(
        self, states: list[str] | None = None, **kwargs: Any
    ) -> list[Any]:
        return [
            _MockCandidate(cid, content) for cid, content in self.candidates
        ]


class _MockCandidate:
    def __init__(self, id: str, content: str) -> None:
        self.id = id
        self.content = content


def test_pipeline_training(tmp_path: Path) -> None:
    geolearn_dir = tmp_path / "geolearn"
    geolearn_dir.mkdir()

    cache = EmbeddingCache(geolearn_dir)
    cache.insert("a1", np.ones(8, dtype=np.float32))
    cache.insert("a2", -np.ones(8, dtype=np.float32))

    provider = _StaticProvider([
        ("c1", json.dumps({"asset_id": "a1", "label": 1, "crop_type": "wheat", "region": "khuzestan"})),
        ("c2", json.dumps({"asset_id": "a2", "label": 0, "crop_type": "wheat", "region": "khuzestan"})),
        ("c3", json.dumps({"asset_id": "a3", "label": 1})),  # proposed → provider filters out
    ])
    # Provider-level state filter: exclude non-verified/supported candidates.
    provider.candidates = provider.candidates[:2]

    pipeline = TrainingPipeline(geolearn_dir, candidate_source=provider)
    p = pipeline.pending_count()
    assert p["total_pending"] == 2
    assert p["by_key"]["wheat__khuzestan"] == 2

    res = pipeline.train_on_feedback()
    assert "wheat__khuzestan" in res
    assert res["wheat__khuzestan"]["samples_trained"] == 2
    assert res["wheat__khuzestan"]["total_n_samples"] == 2

    p2 = pipeline.pending_count()
    assert p2["total_pending"] == 0


def test_pipeline_no_provider_is_noop(tmp_path: Path) -> None:
    geolearn_dir = tmp_path / "geolearn_none"
    geolearn_dir.mkdir()
    pipeline = TrainingPipeline(geolearn_dir, candidate_source=None)
    assert pipeline.pending_count() == {"total_pending": 0, "by_key": {}}
    assert pipeline.train_on_feedback() == {}


def test_pipeline_progress_cb(tmp_path: Path) -> None:
    geolearn_dir = tmp_path / "geolearn_progress"
    geolearn_dir.mkdir()
    cache = EmbeddingCache(geolearn_dir)
    for i in range(4):
        cache.insert(f"a{i}", np.full(8, float(i), dtype=np.float32))
    provider = _StaticProvider([
        (f"c{i}", json.dumps({"asset_id": f"a{i}", "label": i % 2, "crop_type": "corn", "region": "fars"}))
        for i in range(4)
    ])
    pipeline = TrainingPipeline(geolearn_dir, candidate_source=provider)

    events: list[tuple[str, int, int]] = []

    def cb(stage: str, i: int, n: int) -> None:
        events.append((stage, i, n))
        if i == 1:
            raise RuntimeError("progress consumer blew up")

    res = pipeline.train_on_feedback(batch_size=2, progress_cb=cb)
    assert "corn__fars" in res
    assert len(events) == 2  # 4 samples, batch_size=2 → 2 batches
    assert events[0] == ("corn__fars", 1, 2)
    assert events[-1] == ("corn__fars", 2, 2)  # callback survived its own raise


def test_pipeline_with_mock_facade(tmp_path: Path) -> None:
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

    pipeline = TrainingPipeline(geolearn_dir, candidate_source=ws)
    pending = pipeline.pending_count()
    assert pending["total_pending"] == 2
    assert pending["by_key"]["barley__fars"] == 2
    assert ws.queried_states == ["verified", "supported"]

    res = pipeline.train_on_feedback()
    assert "barley__fars" in res
    assert res["barley__fars"]["samples_trained"] == 2


def test_pipeline_rollback_on_revocation(tmp_path: Path) -> None:
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
    pipeline = TrainingPipeline(geolearn_dir, candidate_source=ws)

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
