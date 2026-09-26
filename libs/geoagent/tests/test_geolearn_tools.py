"""Unit tests for GeoLearn tool handlers in GeoAgent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext
from geoagent.store import Store
from geoagent.tools import geolearn_tools


def _create_ctx(tmp_path: Path) -> tuple[Registry, RunContext]:
    registry = Registry()
    settings = AgentSettings(workspace=tmp_path / "ws")
    settings.workspace.mkdir(parents=True, exist_ok=True)
    store = Store(settings.workspace / "agent.db")
    ctx = RunContext(
        store=store,
        workspace_dir=settings.workspace,
        sandbox_roots=settings.resolve_sandbox_roots(),
        settings=settings,
    )
    return registry, ctx


def test_geo_train_on_feedback(tmp_path: Path) -> None:
    registry, ctx = _create_ctx(tmp_path)

    mock_pipeline = MagicMock()
    mock_pipeline.train_on_feedback.return_value = {
        "status": "trained",
        "trained_count": 3,
        "feedback_ids": ["fb1", "fb2", "fb3"],
    }

    with patch("geoagent.tools.geolearn_tools._get_pipeline", return_value=mock_pipeline):
        res = registry.call(
            "geo_train_on_feedback",
            {"feedback_ids": ["fb1", "fb2"], "batch_size": 5},
            ctx,
        )
        assert res.status == "ok"
        assert res.value["trained_count"] == 3
        mock_pipeline.train_on_feedback.assert_called_once_with(
            feedback_ids=["fb1", "fb2"], batch_size=5
        )


def test_geo_pending_training_count(tmp_path: Path) -> None:
    registry, ctx = _create_ctx(tmp_path)

    mock_pipeline = MagicMock()
    mock_pipeline.pending_count.return_value = 7

    with patch("geoagent.tools.geolearn_tools._get_pipeline", return_value=mock_pipeline):
        res = registry.call("geo_pending_training_count", {}, ctx)
        assert res.status == "ok"
        assert res.value == 7


def test_geo_select_region(tmp_path: Path) -> None:
    registry, ctx = _create_ctx(tmp_path)

    mock_store = MagicMock()
    mock_store.get_or_create_key.return_value = ("wheat", "khuzestan")

    with patch("geoagent.tools.geolearn_tools._get_store", return_value=mock_store):
        res = registry.call(
            "geo_select_region",
            {"crop_type": "wheat", "region": "khuzestan", "sub_region": "east"},
            ctx,
        )
        assert res.status == "ok"
        assert res.value == {"key": ("wheat", "khuzestan")}
        mock_store.get_or_create_key.assert_called_once_with("wheat", "khuzestan", "east")


def test_geo_user_settings_get_and_update(tmp_path: Path) -> None:
    registry, ctx = _create_ctx(tmp_path)
    (ctx.workspace_dir / "geolearn").mkdir(parents=True, exist_ok=True)

    # 1. Get default settings
    res_get = registry.call("geo_get_user_settings", {"user_id": "user_1"}, ctx)
    assert res_get.status == "ok"
    assert res_get.value["user_id"] == "user_1"
    assert "confidence_threshold" in res_get.value

    # 2. Update settings
    res_update = registry.call(
        "geo_update_user_settings",
        {
            "user_id": "user_1",
            "partial_settings": {
                "confidence_threshold": 0.85,
                "preferred_classifier": "sgd",
            },
        },
        ctx,
    )
    assert res_update.status == "ok"
    assert res_update.value["confidence_threshold"] == 0.85
    assert res_update.value["preferred_classifier"] == "sgd"


def test_geo_export_for_edge(tmp_path: Path) -> None:
    registry, ctx = _create_ctx(tmp_path)

    mock_clf = MagicMock()
    mock_clf.export_for_edge.return_value = {
        "status": "exported",
        "output_dir": str(tmp_path / "edge_out"),
    }
    mock_store = MagicMock()
    mock_store.get_classifier.return_value = mock_clf

    with patch("geoagent.tools.geolearn_tools._get_store", return_value=mock_store):
        # With relative dir and key
        res = registry.call(
            "geo_export_for_edge",
            {"output_dir": "edge_models", "key": ["wheat", "fars"]},
            ctx,
        )
        assert res.status == "ok"
        assert res.value["status"] == "exported"

        # With default key inside workspace
        res_default = registry.call(
            "geo_export_for_edge",
            {"output_dir": str(ctx.workspace_dir / "edge_models")},
            ctx,
        )
        assert res_default.status == "ok"


def test_geo_versioning_list_and_rollback(tmp_path: Path) -> None:
    registry, ctx = _create_ctx(tmp_path)
    (ctx.workspace_dir / "geolearn").mkdir(parents=True, exist_ok=True)

    from geolearn.versioning import ModelVersion, ModelVersionManager

    with patch.object(ModelVersionManager, "list_versions") as mock_list, patch.object(
        ModelVersionManager, "rollback_to"
    ) as mock_rb:
        mock_list.return_value = [
            ModelVersion(
                key=("wheat", "khuzestan"),
                version=1,
                timestamp="2023-01-01T00:00:00Z",
                n_samples=100,
                sha256="abc123hash",
            )
        ]
        mock_rb.return_value = True

        # List with key
        res_list = registry.call(
            "geo_list_model_versions",
            {"key": ["wheat", "khuzestan"]},
            ctx,
        )
        assert res_list.status == "ok"
        assert len(res_list.value) == 1
        assert res_list.value[0]["version"] == 1

        # Rollback success
        res_rb = registry.call(
            "geo_rollback_model",
            {"key": ["wheat", "khuzestan"], "version": 1},
            ctx,
        )
        assert res_rb.status == "ok"
        assert res_rb.value == {"rolled_back": True}

        # Rollback failure
        mock_rb.return_value = False
        res_rb_fail = registry.call(
            "geo_rollback_model",
            {"key": ["wheat", "khuzestan"], "version": 99},
            ctx,
        )
        assert res_rb_fail.status == "failed"
        assert res_rb_fail.value == {"rolled_back": False}


def test_geolearn_tools_real_store_and_pipeline_getters(tmp_path: Path) -> None:
    _, ctx = _create_ctx(tmp_path)
    (ctx.workspace_dir / "geolearn").mkdir(parents=True, exist_ok=True)

    pipeline = geolearn_tools._get_pipeline(ctx)
    assert pipeline is not None
    store = geolearn_tools._get_store(ctx)
    assert store is not None
