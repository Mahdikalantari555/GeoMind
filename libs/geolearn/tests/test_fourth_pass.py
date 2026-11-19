"""Counterexamples from the fourth QA pass: geolearn versioning + online learning."""
from __future__ import annotations

import numpy as np
import pytest
from geolearn.classifier import OnlineClassifier
from geolearn.online import OnlineScheduler
from geolearn.versioning import ModelVersionManager


def _manager(tmp_path):
    return ModelVersionManager(tmp_path)


def _fitted(offset: float) -> OnlineClassifier:
    clf = OnlineClassifier()
    clf.partial_fit(
        np.array([[offset, 1.0], [1.0, 0.0]]),
        np.array([0, 1]),
        classes=[0, 1],
    )
    return clf


def test_scheduler_rejects_nonpositive_batch(tmp_path):
    with pytest.raises(ValueError):
        OnlineScheduler(batch_size=0)
    with pytest.raises(ValueError):
        OnlineScheduler(batch_size=-3)
    OnlineScheduler(batch_size=1)  # boundary stays valid


def test_version_numbers_are_per_crop_region_sub_region(tmp_path):
    mgr = _manager(tmp_path)
    mgr.save_version(("crop", "r1", "north"), _fitted(0.1))
    south = mgr.save_version(("crop", "r1", "south"), _fitted(0.2))
    assert south.version == 1, "the counter must not be shared with another sub-region"
    north_versions = mgr.list_versions(("crop", "r1", "north"))
    assert [(v.key, v.version) for v in north_versions] == [((("crop", "r1", "north")), 1)]
    assert [v.version for v in mgr.list_versions(("crop", "r1", "south"))] == [1]


def test_rollback_of_one_sub_region_cannot_restore_another(tmp_path):
    mgr = _manager(tmp_path)
    mgr.save_version(("crop", "r1", "north"), _fitted(0.1))
    south = mgr.save_version(("crop", "r1", "south"), _fitted(0.9))
    north_before = mgr.active_hash(("crop", "r1", "north"))
    assert mgr.rollback_to(("crop", "r1", "north"), 2) is False
    assert mgr.active_hash(("crop", "r1", "north")) == north_before
    assert mgr.active_hash(("crop", "r1", "south")) == south.sha256


def test_rollback_refuses_versions_from_a_different_sub_region(tmp_path):
    mgr = _manager(tmp_path)
    mgr.save_version(("crop", "r1", "north"), _fitted(0.1))
    south = mgr.save_version(("crop", "r1", "south"), _fitted(0.5))
    mgr.save_version(("crop", "r1", "north"), _fitted(0.7))
    # north owns versions 1 and 2; south owns only version 1. Resolving south's
    # rollback from north's rows restores the wrong model file.
    assert mgr.rollback_to(("crop", "r1", "south"), 2) is False
    assert mgr.active_hash(("crop", "r1", "south")) == south.sha256
