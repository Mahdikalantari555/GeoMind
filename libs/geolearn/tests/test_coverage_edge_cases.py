"""Comprehensive unit tests covering edge cases to exceed 95% coverage across geolearn."""

import pickle
from pathlib import Path

import numpy as np
import pytest
from geolearn.classifier import ClassifierChoice, OnlineClassifier
from geolearn.confidence import ConfidenceModel, shannon_entropy
from geolearn.frozen_adapter import FrozenEmbeddingAdapter
from geolearn.online import OnlineScheduler, SimpleDriftDetector
from geolearn.versioning import ModelVersionManager


def test_classifier_kmeans_and_setstate_branches(tmp_path: Path) -> None:
    # Unknown classifier choice raises ValueError
    with pytest.raises(ValueError):
        OnlineClassifier(choice="UNKNOWN_CHOICE")  # type: ignore[arg-type]

    # Incremental KMeans with y labels and classes
    km_clf = OnlineClassifier(choice=ClassifierChoice.INCREMENTAL_KMEANS)
    X = np.array([[1.0, 2.0], [2.0, 3.0], [5.0, 6.0], [6.0, 7.0]], dtype=np.float32)
    y = np.array([0, 0, 1, 1])
    km_clf.fit(X, y=y, classes=[0, 1])
    assert km_clf.is_fitted
    assert len(km_clf.classes_) == 2
    preds = km_clf.predict(X)
    assert len(preds) == 4
    probas = km_clf.predict_proba(X)
    assert probas.shape == (4, 2)

    # Incremental KMeans with classes but no y
    km_unsupervised = OnlineClassifier(choice=ClassifierChoice.INCREMENTAL_KMEANS)
    km_unsupervised.fit(X, classes=[0, 1])
    assert km_unsupervised.is_fitted

    # Incremental KMeans partial_fit with classes and y
    km_pf = OnlineClassifier(choice=ClassifierChoice.INCREMENTAL_KMEANS)
    km_pf.partial_fit(X, y=y, classes=[0, 1])
    assert km_pf.is_fitted
    km_pf.partial_fit(X, y=y)

    # Incremental KMeans partial_fit with classes and no y
    km_pf2 = OnlineClassifier(choice=ClassifierChoice.INCREMENTAL_KMEANS)
    km_pf2.partial_fit(X, classes=[0, 1])
    assert km_pf2.is_fitted

    # Single-class partial_fit for supervised classifier
    sgd = OnlineClassifier(choice=ClassifierChoice.SGD)
    sgd.fit(X[:2], y=[1, 1], classes=[1])
    assert sgd.is_fitted

    # __setstate__ backwards compatibility
    empty_clf = OnlineClassifier.__new__(OnlineClassifier)
    empty_clf.__setstate__({})
    assert empty_clf.choice == ClassifierChoice.SGD
    assert empty_clf.n_samples_ == 0
    assert empty_clf.random_state == 42

    # Save and load with invalid object
    bad_file = tmp_path / "bad.pkl"
    with open(bad_file, "wb") as f:
        pickle.dump({"not": "a classifier"}, f)
    with pytest.raises(TypeError, match="Loaded object is not OnlineClassifier"):
        OnlineClassifier.load(bad_file)


def test_online_scheduler_branches() -> None:
    scheduler = OnlineScheduler(batch_size=2, min_interval_s=100.0)
    clf = OnlineClassifier()
    clf.fit([[1.0, 2.0], [2.0, 3.0]], [0, 1])

    # should_train on empty buffer
    assert not scheduler.should_train()

    # Sample as object with embedding and label attributes
    class SampleObj:
        def __init__(self, emb, lbl):
            self.embedding = emb
            self.label = lbl

    # Sample as dict
    sample_dict = {"embedding": [1.5, 2.5], "label": 0}
    sample_obj = SampleObj([2.5, 3.5], 1)

    scheduler.maybe_train(clf, new_samples=[sample_dict, sample_obj])
    # Batch size was 2, so should have trained
    assert len(scheduler.buffer) == 0

    # Test step with force=True
    scheduler.add([3.0, 4.0], 1)
    assert len(scheduler.buffer) == 1
    scheduler.step(clf, force=True)
    assert len(scheduler.buffer) == 0

    # Test flush
    scheduler.add([3.0, 4.0], 1)
    scheduler.flush(clf)
    assert len(scheduler.buffer) == 0

    # Drift triggers training and clears its latch (F-099)
    dd = SimpleDriftDetector(error_rate_threshold=0.1, window=5)
    dd.detected = True
    drift_scheduler = OnlineScheduler(batch_size=1, drift_detector=dd)
    drift_scheduler.add([1.0, 1.0], 0)
    assert drift_scheduler.should_train()
    assert drift_scheduler.maybe_train(clf)
    assert dd.detected is False


def test_version_manager_rollback_and_sync(tmp_path: Path) -> None:
    models_dir = tmp_path / "models"
    vm = ModelVersionManager(models_dir)
    key = ("wheat", "khuzestan")

    clf = OnlineClassifier()
    clf.fit([[1.0, 2.0], [2.0, 3.0]], [0, 1])

    # Save initial versions
    v1 = vm.save_version(key, clf, n_samples=2)
    clf.fit([[1.1, 2.1], [2.1, 3.1]], [0, 1])
    vm.save_version(key, clf, n_samples=4)
    versions = vm.list_versions(key)
    assert len(versions) == 2

    # Rollback to non-existent version returns False
    assert not vm.rollback_to(key, version=999)

    # Rollback to v1 succeeds
    assert vm.rollback_to(key, version=v1.version)

    # Garbage collect older versions
    removed = vm.garbage_collect(key, keep=1)
    assert len(removed) >= 1

    # Create dummy disk version to test _sync_disk_versions
    key_dir = vm._key_dir(key)
    disk_v99 = key_dir / "0099_2026-01-01T00-00-00Z.pkl"
    clf.save(disk_v99)
    # Sync disk versions
    vm._sync_disk_versions()
    synced = vm.list_versions(key)
    assert any(v.version == 99 for v in synced)

    # db_path fallback branches
    dir_with_geolearn_db = tmp_path / "ws_sub"
    (dir_with_geolearn_db / "geolearn").mkdir(parents=True)
    (dir_with_geolearn_db / "geolearn" / "geolearn.db").touch()
    vm_sub = ModelVersionManager(dir_with_geolearn_db)
    assert vm_sub.db_path.exists()



def test_persistence_hierarchical_fallback(tmp_path: Path) -> None:
    from geolearn.persistence import ClassifierStore

    store = ClassifierStore(tmp_path)
    parent_clf = OnlineClassifier()
    parent_clf.fit([[1.0, 2.0], [-1.0, -2.0]], [1, 0])
    store.save_classifier(("wheat", "khuzestan"), parent_clf, n_samples=35)

    # Request child key that doesn't exist -> should inherit from parent
    child_clf = store.get_classifier(("wheat", "khuzestan", "field_south"))
    assert child_clf.is_fitted
    assert list(child_clf.predict([[1.0, 2.0]])) == [1]

    # Predict with n_samples >= 30 and user_id
    res = store.predict(
        [[1.0, 2.0]],
        key=("wheat", "khuzestan"),
        confidence_model=ConfidenceModel(threshold=0.6),
        user_id="user_123",
    )
    assert len(res.labels) == 1

    # partial_fit without scheduler
    store_no_sched = ClassifierStore(tmp_path / "nosched", scheduler=None)
    store_no_sched.partial_fit(("wheat", "khuzestan"), [[1.0, 2.0]], [1], classes=[0, 1])
    assert store_no_sched.get_n_samples(("wheat", "khuzestan")) == 1


def test_online_scheduler_time_trigger() -> None:
    sched = OnlineScheduler(batch_size=10, min_interval_s=5.0)
    sched.add([1.0, 2.0], 1)
    sched.last_train_time = 100.0
    # Before interval elapsed
    assert not sched.should_train(current_time=102.0)
    # After interval elapsed
    assert sched.should_train(current_time=110.0)


def test_profiles_and_settings_db_suffix(tmp_path: Path) -> None:
    from geolearn.profiles import ProfileStore
    from geolearn.user_settings import UserSettingsStore

    db_file = tmp_path / "custom.db"
    p_store = ProfileStore(db_file)
    assert p_store.db_path == db_file

    u_store = UserSettingsStore(db_file)
    assert u_store.db_path == db_file


def test_association_map_edge_branches() -> None:
    from geolearn.association import AssociationMap, compute_embedding_hash

    # String input to hash
    assert compute_embedding_hash("string_hash") == "string_hash"

    # Invalid half life
    with pytest.raises(ValueError, match="half_life_days must be positive"):
        AssociationMap(half_life_days=0)

    am = AssociationMap(half_life_days=30)
    am.decay(-5.0)  # non-positive decay returns immediately

    # Update with dt_days
    am.update([1.0, 2.0], label=0, dt_days=10.0)

    # Blend with classes not present in association map
    blended = am.blend(np.array([0.5, 0.5]), [1.0, 2.0], classes=[99, 100])
    assert np.allclose(blended, [0.5, 0.5])




def test_frozen_adapter_empty_cache_fallback(tmp_path: Path) -> None:
    from geolearn.cache import EmbeddingCache

    cache = EmbeddingCache(workspace_dir=tmp_path)
    adapter = FrozenEmbeddingAdapter(cache=cache, k=3)
    res = adapter.predict([[1.0, 2.0]], classifier=None)
    assert res.abstain is True
    assert res.labels == [0]
    assert res.confidence == [0.0]



def test_training_pipeline_empty_and_fallback(tmp_path: Path) -> None:
    from geolearn.training_pipeline import TrainingPipeline

    pipeline = TrainingPipeline(
        geolearn_dir=tmp_path / "geolearn",
        candidate_source=None,
    )
    # When no candidates exist
    res = pipeline.train_on_feedback()
    assert res == {}
    counts = pipeline.pending_count()
    assert counts["total_pending"] == 0



def test_confidence_and_entropy_edge_cases() -> None:
    # Shannon entropy empty or all zero
    assert shannon_entropy([]) == 0.0
    assert shannon_entropy([0.0, 0.0]) == 0.0

    from geolearn.calibration import IsotonicCalibrator

    # ConfidenceModel with IsotonicCalibrator instance and evaluate
    iso = IsotonicCalibrator()
    cm = ConfidenceModel(threshold=0.5, calibration_curve=iso)
    confs, abstain = cm.evaluate([[0.8, 0.2], [0.6, 0.4]])
    assert len(confs) == 2
    assert isinstance(abstain, (bool, np.bool_))
    assert cm.is_abstain(0.2) is True
    assert cm.is_abstain(0.8) is False


def test_key_normalization_and_feedback_rollback(tmp_path: Path) -> None:
    vm = ModelVersionManager(tmp_path / "ws")
    # Test key formats
    assert vm._normalize_key("wheat.khuzestan.sub") == ("wheat", "khuzestan", "sub")
    assert vm._normalize_key("wheat__khuzestan__sub") == ("wheat", "khuzestan", "sub")
    assert vm._normalize_key("corn__iowa") == ("corn", "iowa")
    assert vm._normalize_key("barley") == ("barley", "global")
    with pytest.raises(TypeError, match="Unsupported key format"):
        vm._normalize_key(12345)  # type: ignore[arg-type]

    # Feedback rollback
    clf = OnlineClassifier()
    clf.fit([[1.0, 2.0], [2.0, 3.0]], [0, 1])
    key = ("rice", "gilan")
    v1 = vm.save_version(key, clf, feedback_ids=["fb_good"])
    clf.fit([[1.1, 2.1], [2.1, 3.1]], [0, 1])
    vm.save_version(key, clf, feedback_ids=["fb_bad"])

    res = vm.rollback_feedback("fb_bad")
    assert len(res) == 1
    assert res[0][1] == v1.version


def test_calibration_and_classifier_uncovered_paths() -> None:
    from geolearn.calibration import (
        CalibrationCurve,
        IsotonicCalibrator,
        prediction_entropy,
    )

    # prediction_entropy with all zeros
    assert prediction_entropy([0.0, 0.0]) == 0.0

    # IsotonicCalibrator calibrate with isotonic method
    scores = np.linspace(0.1, 0.9, 25)
    targets = (scores > 0.5).astype(int)
    cal_iso = IsotonicCalibrator(min_samples_isotonic=20)
    cal_iso.fit(scores, targets)
    assert cal_iso.method == "isotonic"
    val = cal_iso.calibrate(0.7)
    assert 0.0 <= val <= 1.0

    # CalibrationCurve fit buffer >= 10
    cc = CalibrationCurve(window_size=20)
    for i in range(12):
        cc.add_observation(0.1 * (i % 10), i % 2)
    assert cc.calibrator.method != "identity"



