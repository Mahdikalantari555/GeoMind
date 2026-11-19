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


def test_version_filenames_do_not_collide_within_one_second(tmp_path):
    mgr = _manager(tmp_path)
    first = mgr.save_version(("crop", "r1"), _fitted(0.1))
    second = mgr.save_version(("crop", "r1"), _fitted(0.9))
    assert first.sha256 != second.sha256
    assert (tmp_path / "geolearn" / "models").rglob("*.pkl")


def test_legacy_two_part_database_is_migrated_without_losing_versions(tmp_path):
    """A DB created before sub-regions existed must be rebuilt, not patched.

    Adding the column with `ALTER TABLE` left the primary key at
    `(key_crop, key_region, version)`, so saving a sub-region version still
    replaced its sibling's row, and every legacy row came back with a bogus
    sub-region parsed out of the key string.
    """
    import sqlite3

    db = tmp_path / "geolearn.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE model_versions (
            key_crop TEXT NOT NULL, key_region TEXT NOT NULL, key TEXT NOT NULL,
            version INTEGER NOT NULL, timestamp TEXT NOT NULL, n_samples INTEGER NOT NULL,
            sha256 TEXT NOT NULL, file_path TEXT NOT NULL, feedback_ids TEXT NULL,
            PRIMARY KEY (key_crop, key_region, version)
        )
        """
    )
    legacy = [
        ("crop", "r1", "crop__r1__north", 1, "2026-01-01T00:00:00Z"),
        ("crop", "r1", "crop__r1__south", 2, "2026-01-02T00:00:00Z"),
        ("crop", "r1", "crop__r1", 3, "2026-01-03T00:00:00Z"),
    ]
    for crop, region, key, version, ts in legacy:
        conn.execute(
            "INSERT INTO model_versions VALUES (?,?,?,?,?,?,?,?,NULL)",
            (crop, region, key, version, ts, 5, f"s{version}", f"p{version}"),
        )
    conn.commit()
    conn.close()

    mgr = _manager(tmp_path)
    assert [(v.key, v.version) for v in mgr.list_versions(("crop", "r1", "north"))] == [
        (("crop", "r1", "north"), 1)
    ]
    assert [(v.key, v.version) for v in mgr.list_versions(("crop", "r1", "south"))] == [
        (("crop", "r1", "south"), 2)
    ]
    assert [(v.key, v.version) for v in mgr.list_versions(("crop", "r1"))] == [
        (("crop", "r1"), 3)
    ]

    # The rebuilt primary key must let a new north version coexist with south's.
    new = mgr.save_version(("crop", "r1", "north"), _fitted(0.7))
    assert new.version == 2
    assert {v.version for v in mgr.list_versions(("crop", "r1", "south"))} == {2}
    assert {v.version for v in mgr.list_versions(("crop", "r1", "north"))} == {1, 2}
    # Migration is idempotent across reopen.
    assert len(ModelVersionManager(tmp_path).list_versions(None)) == 4
