"""Counterexamples from the fourth QA pass: tool registry, playbooks, agent loop.

Synthetic data only; no network.
"""
from __future__ import annotations

import json

import pytest

from geoagent.agent import AgentCore
from geoagent.config import AgentSettings
from geoagent.llm.base import ChatResponse, ToolCall
from geoagent.playbooks import (
    PlaybookError,
    draft_playbook_text,
    load_playbooks,
    parse_playbook,
    register_playbook_tools,
    save_playbook,
)
from geoagent.registry import (
    Registry,
    RunContext,
    ToolDefinition,
    ToolResult,
)
from geoagent.store import Store


def _ctx(tmp_path, max_tool_calls: int = 8) -> RunContext:
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    return RunContext(
        store=Store(tmp_path / "agent.db"),
        workspace_dir=workspace,
        sandbox_roots=[workspace],
        settings=AgentSettings(workspace=workspace),
        max_tool_calls=max_tool_calls,
    )


# ── schema validation ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("args", "schema"),
    [
        ({"top_k": 9999}, {"type": "object", "properties": {"top_k": {"type": "integer", "minimum": 1, "maximum": 50}}}),
        ({"bbox": [0, 0, 1]}, {"type": "object", "properties": {"bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4}}}),
        ({"name": "x", "extra": 1}, {"type": "object", "properties": {"name": {"type": "string"}}, "additionalProperties": False}),
        ({"name": ""}, {"type": "object", "properties": {"name": {"type": "string", "minLength": 1}}}),
    ],
)
def test_out_of_contract_arguments_are_rejected(args, schema):
    from geoagent.registry import _validate

    assert _validate(args, schema, "$"), f"{args} should not validate"


def test_registry_refuses_out_of_range_arguments(tmp_path):
    reg = Registry()

    @reg.register(
        ToolDefinition(
            name="k",
            description="k",
            params={
                "type": "object",
                "properties": {"top_k": {"type": "integer", "minimum": 1, "maximum": 5}},
                "additionalProperties": False,
            },
        )
    )
    def k(args, ctx):
        return args["top_k"]

    ctx = _ctx(tmp_path)
    assert reg.call("k", {"top_k": 99}, ctx).status == "validation_error"
    assert reg.call("k", {"top_k": 1, "junk": True}, ctx).status == "validation_error"
    assert reg.call("k", {"top_k": 3}, ctx).status == "ok"


# ── sandbox ────────────────────────────────────────────────────────────────


def test_glob_arguments_are_sandboxed(tmp_path):
    """`raster_glob` is a path argument even though it has no path suffix."""
    reg = Registry()

    @reg.register(
        ToolDefinition(
            name="globber",
            description="g",
            params={
                "type": "object",
                "properties": {"raster_glob": {"type": "string"}},
                "required": ["raster_glob"],
            },
        )
    )
    def globber(args, ctx):
        return [str(p) for p in ctx.workspace_dir.glob(args["raster_glob"])]

    ctx = _ctx(tmp_path)
    (tmp_path / "outside.tif").write_text("x")
    res = reg.call("globber", {"raster_glob": "../../**/*.tif"}, ctx)
    assert res.status == "validation_error"
    assert "sandbox" in (res.error or "").lower()


def test_absolute_glob_pattern_is_sandboxed(tmp_path):
    reg = Registry()

    @reg.register(
        ToolDefinition(
            name="globber2",
            description="g",
            params={"type": "object", "properties": {"pattern": {"type": "string"}}},
        )
    )
    def globber2(args, ctx):
        return args["pattern"]

    res = reg.call("globber2", {"pattern": "/etc/*.conf"}, _ctx(tmp_path))
    assert res.status == "validation_error"


# ── playbooks ──────────────────────────────────────────────────────────────


def test_saving_a_playbook_cannot_escape_the_playbook_directory(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    with pytest.raises(PlaybookError):
        save_playbook(workspace, "../escape", "---\nname: escape\nsteps:\n  - tool: a\n---\n")
    assert not (workspace / "escape.md").exists()


@pytest.mark.parametrize("bad", [".", "..", "a/../b", ""])
def test_playbook_names_must_be_slug_like(tmp_path, bad):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    with pytest.raises(PlaybookError):
        save_playbook(workspace, bad, "---\nname: x\nsteps:\n  - tool: a\n---\n")


def test_two_files_declaring_the_same_playbook_do_not_crash_registration(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "playbooks").mkdir(parents=True)
    for name in ("one", "two"):
        (workspace / "playbooks" / f"{name}.md").write_text(
            "---\nname: duplicate\nsteps:\n  - tool: a\n---\n"
        )
    settings = AgentSettings(workspace=workspace)

    @Registry().register(ToolDefinition(name="a", description="a"))
    def _a(args, ctx):  # pragma: no cover - registration only
        return ToolResult()

    found = load_playbooks(workspace)
    assert len(found) == 2
    registry = Registry()

    @registry.register(ToolDefinition(name="a", description="a"))
    def a(args, ctx):
        return ToolResult(status="ok", value={})

    register_playbook_tools(registry, settings)  # must not raise
    assert "pb_duplicate" in registry.names()


def test_playbook_with_a_missing_template_value_is_rejected(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "playbooks").mkdir(parents=True)
    (workspace / "playbooks" / "gaps.md").write_text(
        "---\nname: gaps\nparams:\n  known: {type: string}\nsteps:\n"
        "  - tool: a\n    args: {value: '{{params.unknown}}'}\n---\n"
    )
    registry = Registry()

    @registry.register(ToolDefinition(name="a", description="a"))
    def a(args, ctx):
        return ToolResult(status="ok", value=args)

    register_playbook_tools(registry, AgentSettings(workspace=workspace))
    res = registry.call("pb_gaps", {"known": "x"}, _ctx(tmp_path))
    assert res.status == "validation_error"
    assert "unknown" in (res.error or "")


def test_draft_strips_a_language_tagged_code_fence():
    class _Backend:
        def chat(self, messages, tools=None):
            return ChatResponse(content="```yaml\n---\nname: x\nsteps:\n  - tool: a\n---\n```")

    text = draft_playbook_text(_Backend(), "x", [])
    assert text.startswith("---")
    parse_playbook(text)


# ── agent loop ─────────────────────────────────────────────────────────────


class _ScriptedBackend:
    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools=None):
        return self.script.pop(0)


def _core(tmp_path, backend):
    workspace = tmp_path / "ws"
    workspace.mkdir(exist_ok=True)
    settings = AgentSettings(workspace=workspace, budgets={"max_tool_calls": 2})
    store = Store(workspace / "agent.db")
    registry = Registry()

    @registry.register(
        ToolDefinition(
            name="echo_hits",
            description="hits",
            params={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
                "additionalProperties": False,
            },
        )
    )
    def echo_hits(args, ctx):
        return ToolResult(status="ok", value={"hits": [{"id": "s1", "text": "t"}]})

    return AgentCore(settings, backend, registry, store)


def test_malformed_tool_arguments_are_reported_not_silently_empty(tmp_path):
    """A truncated JSON argument object must not run the tool with `{}`."""
    backend = _ScriptedBackend(
        [
            ChatResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="echo_hits", arguments='{"q":')],
            ),
            ChatResponse(content="done [S1]"),
        ]
    )
    core = _core(tmp_path, backend)
    conv = core.new_conversation("t")
    events: list[str] = []
    core.chat(conv, "go", on_event=events.append)
    tool_runs = core.store.conn.execute("SELECT status, error FROM tool_run").fetchall()
    assert tool_runs and tool_runs[0]["status"] == "validation_error"
    assert "arguments" in (tool_runs[0]["error"] or "").lower()


def test_repeated_identical_failing_tool_call_cannot_burn_the_budget_silently(tmp_path):
    """The loop must stop repeating one identical failing call forever."""
    failing = ChatResponse(
        content=None,
        tool_calls=[ToolCall(id="x", name="echo_hits", arguments='{"q": 1}')],
    )
    backend = _ScriptedBackend([failing, failing, failing, failing, failing])
    core = _core(tmp_path, backend)
    conv = core.new_conversation("t")
    answer = core.chat(conv, "go")
    assert "budget" in answer.lower() or "failed" in answer.lower()
    calls = core.store.conn.execute("SELECT COUNT(*) AS n FROM tool_run").fetchone()["n"]
    assert calls <= 3


def test_citation_registry_does_not_grow_across_turns(tmp_path):
    """S-keys from an earlier tool call must not authorise new citations."""
    backend = _ScriptedBackend(
        [
            ChatResponse(content=None, tool_calls=[ToolCall(id="1", name="echo_hits", arguments='{"q":"a"}')]),
            ChatResponse(content="answer one [S1]"),
            ChatResponse(content="answer two [S1]"),
        ]
    )
    core = _core(tmp_path, backend)
    conv = core.new_conversation("t")
    first = core.chat(conv, "one")
    second = core.chat(conv, "two")
    assert "[S1]" in first
    assert "[S1]" not in second  # no retrieval ran in the second turn
    assert "invalid citation" in second


# ── symbology / advisor (need rasterio + matplotlib) ───────────────────────


def _symbology_env(tmp_path):
    pytest.importorskip("rasterio")
    pytest.importorskip("matplotlib")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    settings = AgentSettings(workspace=workspace)
    registry = Registry()
    from geoagent.tools import gis_tools

    gis_tools.register(registry)
    ctx = RunContext(
        store=Store(workspace / "agent.db"),
        workspace_dir=workspace,
        sandbox_roots=[workspace],
        settings=settings,
    )
    return registry, ctx, workspace


def _classes_geojson(workspace, values):
    features = [
        {
            "type": "Feature",
            "properties": {"class": v},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[i, 0], [i + 1, 0], [i + 1, 1], [i, 1], [i, 0]]],
            },
        }
        for i, v in enumerate(values)
    ]
    path = workspace / "classes.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return "classes.geojson"


def test_symbology_rejects_a_constant_field_instead_of_empty_classes(tmp_path):
    registry, ctx, workspace = _symbology_env(tmp_path)
    src = _classes_geojson(workspace, [1, 1, 1])
    res = registry.call(
        "geo_symbology",
        {
            "input_geojson": src,
            "field": "class",
            "classification": {"scheme": "quantiles", "n_classes": 4},
            "out_png": "map.png",
        },
        ctx,
    )
    assert res.status == "validation_error"
    assert "constant" in (res.error or "")


def test_symbology_manual_breaks_must_cover_every_class(tmp_path):
    registry, ctx, workspace = _symbology_env(tmp_path)
    src = _classes_geojson(workspace, [0, 1, 2])
    # The advisor's old breaks stopped at 1.5, so class 2 was never drawn.
    short = registry.call(
        "geo_symbology",
        {
            "input_geojson": src,
            "field": "class",
            "classification": {"scheme": "manual", "breaks": [-0.5, 0.5, 1.5]},
            "out_png": "bad.png",
        },
        ctx,
    )
    assert short.status == "validation_error"
    full = registry.call(
        "geo_symbology",
        {
            "input_geojson": src,
            "field": "class",
            "classification": {"scheme": "manual", "breaks": [-0.5, 0.5, 1.5, 2.5]},
            "out_png": "good.png",
        },
        ctx,
    )
    assert full.status == "ok", full.error
    assert sum(c["features"] for c in full.value["classes"]) == 3


def test_symbology_rejects_duplicate_manual_breaks(tmp_path):
    registry, ctx, workspace = _symbology_env(tmp_path)
    src = _classes_geojson(workspace, [0, 1])
    res = registry.call(
        "geo_symbology",
        {
            "input_geojson": src,
            "field": "class",
            "classification": {"scheme": "manual", "breaks": [-0.5, 1.5, 1.5, 2.5]},
            "out_png": "dup.png",
        },
        ctx,
    )
    assert res.status == "validation_error"


def test_report_windows_and_dates_reject_impossible_filenames():
    from pathlib import Path

    from geoagent.tools.advisor_tools import _parse_dates

    good = Path("s2_2025-07-01.tif")
    impossible = Path("scene_20241345.tif")
    rolled = Path("img_20250230.tif")
    dated = _parse_dates([good, impossible, rolled])
    assert dated == [("2025-07-01", good)]
