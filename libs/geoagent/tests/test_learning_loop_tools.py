"""Tests for learning-loop tools and the tool-manifest cap."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from geoagent.config import AgentSettings
from geoagent.registry import Registry, RunContext, ToolDefinition
from geoagent.store import Store
from geoagent.tools import learning_loop_tools, memory_tools


def _ctx(tmp_path: Path) -> tuple[Registry, RunContext]:
    registry = Registry()
    settings = AgentSettings(workspace=tmp_path / "ws")
    settings.workspace.mkdir(parents=True, exist_ok=True)
    store = Store(settings.workspace / "agent.db")
    ctx = RunContext(
        store=store, workspace_dir=settings.workspace,
        sandbox_roots=settings.resolve_sandbox_roots(), settings=settings,
    )
    return registry, ctx


def test_learning_loop_tools_registered(tmp_path: Path) -> None:
    registry, _ = _ctx(tmp_path)
    for name in (
        "geo_record_feedback", "geo_review_queue", "geo_review",
        "geo_export_dataset", "geo_export_runs", "list_tools",
    ):
        assert name in registry.names()


def test_geo_record_feedback_maps_to_public_facade(tmp_path: Path) -> None:
    registry, ctx = _ctx(tmp_path)
    memory = MagicMock()
    memory.record_feedback.side_effect = lambda event: event
    memory_tools.set_memory(memory)
    try:
        with patch("geoagent.tools.learning_loop_tools._memory", return_value=memory):
            result = registry.call(
                "geo_record_feedback",
                {"comment": "wrong ET", "rating": 1, "target_refs": ["ans_1", "run_2"]},
                ctx,
            )
        assert result.status == "ok"
        events = [call.args[0] for call in memory.record_feedback.call_args_list]
        assert len(events) == 2
        assert {e.target_type for e in events} == {"answer", "tool_run"}
        assert all(e.payload["comment"] == "wrong ET" for e in events)
        assert all(e.metadata["target_refs"] == ["ans_1", "run_2"] for e in events)
    finally:
        memory_tools.set_memory(None)


def test_geo_review_and_queue_call_facade(tmp_path: Path) -> None:
    registry, ctx = _ctx(tmp_path)
    memory = MagicMock()
    memory.review_example.return_value = True
    example = MagicMock()
    example.model_dump.return_value = {"id": "ex1", "review_state": "pending"}
    memory.get_review_queue.return_value = [example]
    with patch("geoagent.tools.learning_loop_tools._memory", return_value=memory):
        queue = registry.call("geo_review_queue", {}, ctx)
        review = registry.call(
            "geo_review", {"example_id": "ex1", "accept": True, "reviewer_id": "r1"}, ctx,
        )
    assert queue.value["examples"][0]["id"] == "ex1"
    assert review.value == {"changed": True}
    memory.review_example.assert_called_once_with("ex1", accept=True, reviewer_id="r1")


def test_geo_export_dataset_returns_artifact(tmp_path: Path) -> None:
    registry, ctx = _ctx(tmp_path)
    memory = MagicMock()
    exported = tmp_path / "ws" / "rag_eval.jsonl"
    exported.write_text("{}\n", encoding="utf-8")
    memory.export_dataset.return_value = exported
    with patch("geoagent.tools.learning_loop_tools._memory", return_value=memory):
        result = registry.call(
            "geo_export_dataset", {"task_type": "rag_eval", "output_dir": "exports"}, ctx,
        )
    assert result.status == "ok"
    assert result.artifacts and result.artifacts[0].path == str(exported)
    assert result.artifacts[0].sha256  # computed by Registry.call


def test_geo_export_runs_writes_audit_rows(tmp_path: Path) -> None:
    registry, ctx = _ctx(tmp_path)
    ctx.store.record_tool_run(
        conversation_id="c1", turn_id="t1", tool="geo_search", args={},
        args_hash="h", status="budget_refused", latency_ms=3, error=None,
        artifacts=[], from_cache=False,
    )
    result = registry.call(
        "geo_export_runs", {"output_path": "runs.csv", "format": "csv"}, ctx,
    )
    assert result.status == "ok"
    assert result.value["rows"] == 1
    text = (ctx.workspace_dir / "runs.csv").read_text(encoding="utf-8")
    assert "geo_search" in text and "True" in text  # budgets_hit from status


def test_manifest_cap_collapses_lru_families(tmp_path: Path) -> None:
    _, ctx = _ctx(tmp_path)
    registry = Registry(manifest_token_budget=80)
    for i in range(12):
        registry.register(ToolDefinition(name=f"geo_tool_{i}", description="a" * 30))(
            lambda args, ctx: None  # noqa: ARG005
        )
    lines = registry.manifest_lines()
    # Expanded definitions must be within the token budget; overflow families
    # become one-line summaries plus the list_tools escape hatch.
    assert any("list_tools" in line for line in lines)
    assert sum(len(line) // 4 + 1 for line in lines) <= 120
    expanded = registry.call("list_tools", {"family": "geo"}, ctx)
    assert expanded.status == "ok"
    assert len(expanded.value["tools"]) >= 12


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_geo_export_runs_formats(tmp_path: Path, fmt: str) -> None:
    registry, ctx = _ctx(tmp_path)
    result = registry.call(
        "geo_export_runs", {"output_path": f"runs.{fmt}", "format": fmt}, ctx,
    )
    assert result.status == "ok"
    assert (ctx.workspace_dir / f"runs.{fmt}").is_file()
