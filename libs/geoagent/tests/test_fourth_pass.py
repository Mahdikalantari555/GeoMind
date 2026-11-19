"""Counterexamples from the fourth QA pass: tool registry, playbooks, agent loop.

Synthetic data only; no network.
"""
from __future__ import annotations

import csv
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


# ── raster tools: nodata mask and area units ───────────────────────────────


def _write_raster(path, array, *, nodata, crs="EPSG:4326", res=1.0, origin=(0, 1)):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    with rasterio.open(
        path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
        count=1, dtype=str(array.dtype), crs=crs,
        transform=from_origin(origin[0], origin[1], res, res), nodata=nodata,
    ) as dst:
        dst.write(array, 1)


def test_zonal_stats_drops_pixels_masked_by_the_raster_nodata(tmp_path):
    """`rio_mask(filled=False)` masks nodata; `astype` keeps the masked values.

    The tool then converted the array to `np.ndarray`, which silently recovered
    the masked 9.0 and averaged it in: count 4, mean 3.75 for values 1,2,3,9.
    """
    import json as _json

    import numpy as np

    registry, ctx, workspace = _symbology_env(tmp_path)
    from geoagent.tools import gis_tools

    if "geo_zonal_stats" not in registry.names():
        gis_tools.register(registry)
    _write_raster(workspace / "r.tif", np.array([[1.0, 2.0], [3.0, 9.0]], dtype="float32"), nodata=9.0)
    (workspace / "aoi.geojson").write_text(
        _json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"farm_id": "A"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[-1, -1], [3, -1], [3, 3], [-1, 3], [-1, -1]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    res = registry.call(
        "geo_zonal_stats",
        {"raster_tif": "r.tif", "polygons_geojson": "aoi.geojson", "out_csv": "o.csv"},
        ctx,
    )
    assert res.status == "ok", res.error
    assert res.value["lowest_mean_first"][0]["mean"] == 2.0, res.value  # (1+2+3)/3
    rows = list(csv.DictReader((workspace / "o.csv").open(encoding="utf-8")))
    assert float(rows[0]["max"]) == 3.0, rows
    assert float(rows[0]["nodata_share"]) == 0.25, rows


def test_polygonize_reports_area_in_crs_units_not_degrees(tmp_path):
    """A projected (metre) CRS was reported as `area_deg2` via a lon/lat shoelace.

    A 10 m × 10 m pixel is 100 m²; the planar shoelace over metre coordinates
    produced `area_deg2: 500000.0` for a half-raster, i.e. a unit lie.
    """
    import json as _json

    import numpy as np

    pytest.importorskip("rasterio")
    registry, ctx, workspace = _symbology_env(tmp_path)
    from geoagent.tools import gis_tools

    if "geo_polygonize" not in registry.names():
        gis_tools.register(registry)
    arr = np.zeros((100, 100), dtype="int32")
    arr[:50, :] = 1
    arr[50:, :] = 2
    _write_raster(workspace / "u.tif", arr, nodata=-9999, crs="EPSG:32723", res=10.0, origin=(500000, 7000000))
    res = registry.call(
        "geo_polygonize", {"input_tif": "u.tif", "output_geojson": "u.geojson"}, ctx
    )
    assert res.status == "ok", res.error
    fc = _json.loads((workspace / "u.geojson").read_text(encoding="utf-8"))
    for feature in fc["features"]:
        assert "area_m2" in feature["properties"], feature["properties"]
        assert feature["properties"]["area_m2"] == pytest.approx(500_000.0, rel=1e-3)
        assert "area_deg2" not in feature["properties"]


# ── LLM backend URL construction ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://api.example.test/v1", "https://api.example.test/v1/chat/completions"),
        # `"/v1" in segment` also matched "v1beta" and produced
        # ".../v1beta/v1/chat/completions", which 404s on Gemini-compatible
        # endpoints.
        ("https://api.example.test/v1beta", "https://api.example.test/v1beta/chat/completions"),
        ("https://api.example.test/api", "https://api.example.test/api/v1/chat/completions"),
    ],
)
def test_versioned_base_urls_are_not_double_suffixed(base, expected):
    from geoagent.config import ProviderSettings
    from geoagent.llm.openai_compat import OpenAICompatBackend

    settings = AgentSettings(provider=ProviderSettings(base_url=base, api_key="synthetic"))
    assert OpenAICompatBackend(settings)._url == expected
