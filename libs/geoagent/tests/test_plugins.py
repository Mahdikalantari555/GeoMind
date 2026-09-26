"""Custom-tool plugin discovery tests."""

from geoagent.config import AgentSettings
from geoagent.plugins import load_plugin_module, load_plugins
from geoagent.registry import Registry

GOOD_PLUGIN = """\
from geoagent.registry import Registry, ToolDefinition


def register(registry):
    @registry.register(ToolDefinition(name="plugin_hello", description="h"))
    def plugin_hello(args, ctx):
        return {"hello": True}
"""

BROKEN_PLUGIN = "this is not python ((("


def _settings(tmp_path):
    settings = AgentSettings(workspace=tmp_path / "ws")
    (settings.workspace / "plugins").mkdir(parents=True)
    return settings


def test_workspace_plugin_discovered(tmp_path):
    settings = _settings(tmp_path)
    (settings.workspace / "plugins" / "hello.py").write_text(GOOD_PLUGIN)
    registry = Registry()
    loaded = load_plugins(registry, settings.workspace)
    assert loaded == ["plugin:hello"]
    assert "plugin_hello" in registry.names()


def test_broken_plugin_isolated(tmp_path):
    settings = _settings(tmp_path)
    (settings.workspace / "plugins" / "aaa_good.py").write_text(GOOD_PLUGIN)
    (settings.workspace / "plugins" / "zzz_bad.py").write_text(BROKEN_PLUGIN)
    registry = Registry()
    loaded = load_plugins(registry, settings.workspace)
    assert loaded == ["plugin:aaa_good"]


def test_load_plugin_module_returns_none_for_garbage(tmp_path):
    junk = tmp_path / "junk.py"
    junk.write_text(BROKEN_PLUGIN)
    assert load_plugin_module(junk) is None


def test_try_register_and_entrypoint_plugins(tmp_path):
    from unittest.mock import MagicMock, patch

    from geoagent.plugins import _try_register

    reg = Registry()

    # 1. Module without register
    no_reg_mod = MagicMock(spec=[])
    assert _try_register(reg, no_reg_mod) is False

    # 2. Module whose register raises
    bad_reg_mod = MagicMock()
    bad_reg_mod.register.side_effect = RuntimeError("fail")
    assert _try_register(reg, bad_reg_mod) is False

    # 3. Entrypoint plugins
    ep_good = MagicMock()
    ep_good.name = "my_ep"
    ep_good.load.return_value = MagicMock(register=lambda r: None)

    ep_broken = MagicMock()
    ep_broken.name = "broken_ep"
    ep_broken.load.side_effect = ImportError("cannot load")

    with patch("geoagent.plugins._entry_point_plugins", return_value=[("dist1", ep_good), ("dist2", ep_broken)]):
        loaded = load_plugins(reg, tmp_path)
        assert "entrypoint:dist1:my_ep" in loaded

