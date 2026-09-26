"""Unit tests for geoagent.cli using click.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from geoagent.cli import main
from geoagent.config import AgentSettings, write_default_config
from geoagent.llm.base import ChatResponse
from geoagent.registry import ToolResult


def test_cli_version() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower() or "geoagent" in result.output.lower()


def test_cli_init(tmp_path: Path) -> None:
    runner = CliRunner()
    target_dir = tmp_path / "work"
    result = runner.invoke(main, ["init", str(target_dir)])
    assert result.exit_code == 0
    assert (target_dir / "geoagent-workspace" / "runs").is_dir()
    assert (target_dir / "geoagent-workspace" / "playbooks").is_dir()
    assert (target_dir / "agent.yaml").is_file()


def test_cli_tools(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "agent.yaml"
    write_default_config(cfg_path)

    result = runner.invoke(main, ["tools", "--config", str(cfg_path)])
    assert result.exit_code == 0
    assert "geo_search" in result.output or "geo_ingest" in result.output


def test_cli_search(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "agent.yaml"
    write_default_config(cfg_path)

    # Mock registry call to geo_search
    with patch("geoagent.registry.Registry.call") as mock_call:
        mock_call.return_value = ToolResult(status="ok", value={"results": ["found1"]})
        result = runner.invoke(
            main,
            [
                "search",
                "wheat yield",
                "--config",
                str(cfg_path),
                "--bbox",
                "48.0,31.0,49.0,32.0",
                "--date-range",
                "2023-01-01,2023-12-31",
            ],
        )
        assert result.exit_code == 0
        assert "found1" in result.output


def test_cli_ingest(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "agent.yaml"
    write_default_config(cfg_path)
    sample_file = tmp_path / "data.txt"
    sample_file.write_text("sample content", encoding="utf-8")

    with patch("geoagent.registry.Registry.call") as mock_call:
        mock_call.return_value = ToolResult(status="ok", value={"doc_id": "doc_123"})
        result = runner.invoke(
            main,
            ["ingest", str(sample_file), "--collection", "crops", "--config", str(cfg_path)],
        )
        assert result.exit_code == 0
        assert "doc_123" in result.output


def test_cli_chat_backend_failure(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "agent.yaml"
    write_default_config(cfg_path)

    with patch("geoagent.cli.build_backend", side_effect=RuntimeError("no API key")):
        result = runner.invoke(main, ["chat", "--config", str(cfg_path)])
        assert result.exit_code == 0
        assert "LLM setup problem" in result.output


def test_cli_chat_interactive_session(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "agent.yaml"
    write_default_config(cfg_path)

    mock_backend = MagicMock()
    mock_backend.chat.return_value = ChatResponse(content="I am ready.", tool_calls=[])

    user_inputs = "/tools\n/new\n\nhello agent\n/exit\n"
    with patch("geoagent.cli.build_backend", return_value=mock_backend):
        result = runner.invoke(main, ["chat", "--config", str(cfg_path)], input=user_inputs)
        assert result.exit_code == 0
        assert "GeoAgent chat" in result.output
        assert "new conversation" in result.output
        assert "I am ready." in result.output


def test_cli_json_loads_safe() -> None:
    from geoagent.cli import _json_loads_safe

    assert _json_loads_safe('{"a": 1}') == {"a": 1}
    assert _json_loads_safe("invalid json") == {}


def test_cli_playbook_commands(tmp_path: Path) -> None:
    runner = CliRunner()
    cfg_path = tmp_path / "agent.yaml"
    write_default_config(cfg_path)
    settings = AgentSettings(workspace=tmp_path / "ws")
    settings.workspace.mkdir(parents=True, exist_ok=True)
    pb_dir = settings.workspace / "playbooks"
    pb_dir.mkdir(parents=True, exist_ok=True)

    # 1. Playbook list when empty
    with patch("geoagent.cli.load_settings", return_value=settings):
        res_empty = runner.invoke(main, ["playbook", "list", "--config", str(cfg_path)])
        assert res_empty.exit_code == 0
        assert "no playbooks" in res_empty.output

    # Write a sample playbook
    sample_pb = pb_dir / "crop_analysis.md"
    sample_pb.write_text(
        "---\nname: crop_analysis\nversion: 1\nsteps:\n  - tool: geo_search\n    args: {}\n---\nAnalyze crops\n",
        encoding="utf-8",
    )

    with patch("geoagent.cli.load_settings", return_value=settings):
        # 2. Playbook list with items
        res_list = runner.invoke(main, ["playbook", "list", "--config", str(cfg_path)])
        assert res_list.exit_code == 0
        assert "crop_analysis" in res_list.output

        # 3. Playbook show
        res_show = runner.invoke(
            main, ["playbook", "show", "crop_analysis", "--config", str(cfg_path)]
        )
        assert res_show.exit_code == 0
        assert "Analyze crops" in res_show.output

        # 4. Playbook show missing
        res_missing = runner.invoke(
            main, ["playbook", "show", "nonexistent", "--config", str(cfg_path)]
        )
        assert res_missing.exit_code == 0
        assert "not found" in res_missing.output

        # 5. Playbook run
        with patch("geoagent.registry.Registry.call") as mock_call:
            mock_call.return_value = ToolResult(status="ok", value={"step": 1})
            res_run = runner.invoke(
                main,
                [
                    "playbook",
                    "run",
                    "crop-analysis",
                    "--config",
                    str(cfg_path),
                    "--param",
                    'key="val"',
                    "--param",
                    "num=42",
                ],
            )
            assert res_run.exit_code == 0
            assert '"status": "ok"' in res_run.output

        # 6. Playbook save empty conversation
        mock_backend = MagicMock()
        mock_backend.chat.return_value = ChatResponse(
            content="---\nname: new_pb\nversion: 1\nsteps:\n  - tool: geo_search\n    args: {}\n---\nDescription\n"
        )
        with patch("geoagent.cli.build_backend", return_value=mock_backend):
            res_save_empty = runner.invoke(
                main,
                [
                    "playbook",
                    "save",
                    "new_pb",
                    "--config",
                    str(cfg_path),
                    "--conversation",
                    "conv_none",
                ],
            )
            assert res_save_empty.exit_code == 0
            assert "no tool runs" in res_save_empty.output

            # 7. Playbook save with conversation
            from geoagent.store import Store

            store = Store(settings.workspace / "agent.db")
            store.record_tool_run(
                conversation_id="conv_1",
                turn_id="turn_1",
                tool="geo_search",
                args={"query": "test"},
                args_hash="hash1",
                status="ok",
                latency_ms=100,
                error=None,
                artifacts=[],
                from_cache=False,
            )
            store.close()

            res_save = runner.invoke(
                main,
                [
                    "playbook",
                    "save",
                    "new_pb",
                    "--config",
                    str(cfg_path),
                    "--conversation",
                    "conv_1",
                ],
            )
            assert res_save.exit_code == 0
            assert "saved" in res_save.output
