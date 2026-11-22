"""Negative tests for the tool sandbox and trust boundaries (S-018…S-023)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from geodomain import STRESS_SEVERITY_TAXONOMY
from geoagent.config import AgentSettings, CliToolConfig
from geoagent.plugins import load_plugins
from geoagent.registry import Registry, RunContext, ToolDefinition
from geoagent.tools import cli_runner
from geoagent.store import Store


def _ctx(ws: Path, scope: dict[str, list[str]] | None = None) -> RunContext:
    return RunContext(
        store=Store(ws / "agent.db"),
        workspace_dir=ws,
        sandbox_roots=[ws],
        settings=None,
        context_scope=scope,
    )


def _registry_that_writes() -> Registry:
    reg = Registry()

    @reg.register(
        ToolDefinition(
            name="writer",
            description="write tool",
            params={
                "type": "object",
                "properties": {"output_tif": {"type": "string"}},
                "required": ["output_tif"],
                "additionalProperties": False,
            },
        )
    )
    def writer(args: dict[str, Any], ctx: RunContext) -> str:
        Path(args["output_tif"]).write_text("owned")
        return "wrote"

    return reg


def test_absolute_output_path_is_rejected(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    reg = _registry_that_writes()
    ctx = _ctx(ws)
    outside = tmp_path / "victim.tif"

    result = reg.call("writer", {"output_tif": str(outside)}, ctx)
    assert result.status == "validation_error"
    assert not outside.exists()


def test_cli_declared_path_param_is_validated(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    settings = AgentSettings(
        workspace=ws,
        cli_tools={
            "danger": CliToolConfig(
                description="danger",
                argv=["echo", "{src}"],
                path_params=["src"],
            )
        },
    )
    reg = Registry()
    cli_runner.register_from_config(reg, settings)
    ctx = _ctx(ws)
    ctx.settings = settings

    result = reg.call("danger", {"src": "../secret.txt"}, ctx)
    assert result.status == "validation_error"
    assert "sandbox" in result.error.lower() or "outside" in result.error.lower()


def test_plugin_hash_pin_rejects_unpinned_and_modified(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    plugin = ws / "plugins" / "evil.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(registry):\n    pass\n"
    )
    digest = hashlib.sha256(plugin.read_bytes()).hexdigest()

    assert load_plugins(Registry(), ws, {"evil.py": digest}) == ["plugin:evil"]
    assert load_plugins(Registry(), ws, {}) == []  # unpinned → skipped
    plugin.write_text("def register(registry):\n    pass\n# tampered\n")
    assert load_plugins(Registry(), ws, {"evil.py": digest}) == []  # mismatch


def test_nested_context_is_bounded_and_shares_deadline(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = _ctx(ws)
    ctx.max_tool_calls = 2
    inner = ctx.derive()

    # Not the old unbounded 500-call / +880s reset (L-061).
    assert inner.max_tool_calls <= max(
        ctx.max_tool_calls * RunContext.NESTED_FANOUT, 16
    )
    assert inner.deadline == ctx.deadline
    assert inner.shared_budget is ctx.shared_budget

    reg = _registry_that_writes()
    # Write inside the workspace (never the process cwd) so tests leave no junk.
    assert reg.call("writer", {"output_tif": str(ws / "a.tif")}, inner).status == "ok"
    # The nested-call ceiling is global across derived contexts.
    ctx.shared_budget["nested_used"] = RunContext.NESTED_CALL_CEILING
    assert reg.call("writer", {"output_tif": str(ws / "b.tif")}, inner).status == "budget_refused"


def test_classifier_key_traversal_is_rejected() -> None:
    from geolearn.persistence import ClassifierStore

    store = ClassifierStore.__new__(ClassifierStore)
    store.models_dir = Path("/workspace/models")
    with pytest.raises(ValueError, match="Invalid"):
        store._model_path(("wheat", "../../etc"))
    with pytest.raises(ValueError, match="Invalid"):
        store._model_path("wheat..etc")


def test_stress_severity_taxonomy_is_single_cross_lib_source() -> None:
    from geoagent.tools.advisor_tools import CLASS_LABELS as AGENT_LABELS
    from geofront_api.routers.agent.farms import CLASS_LABELS as SERVER_LABELS

    expected = {
        lbl.class_id: lbl.display_name.lower() for lbl in STRESS_SEVERITY_TAXONOMY.labels
    }
    assert AGENT_LABELS == expected
    assert SERVER_LABELS == expected
