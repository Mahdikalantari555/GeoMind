"""Unit tests for geomemory index CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from geomemory.cli.commands.index import index_cmd
from geomemory.core.workspace import GeoMemory


def test_index_cmd_build_and_rebuild(temp_workspace: GeoMemory) -> None:
    runner = CliRunner()
    ws_path = str(temp_workspace.get_workspace_path())

    with patch.object(GeoMemory, "build_index") as mock_build:
        result = runner.invoke(index_cmd, ["build", "-w", ws_path, "--space", "text.test.v1"])
        assert result.exit_code == 0
        mock_build.assert_called_once_with("text.test.v1")
        assert "Built index for space: text.test.v1" in result.output

    with patch.object(GeoMemory, "rebuild_index") as mock_rebuild:
        result = runner.invoke(index_cmd, ["rebuild", "-w", ws_path, "--space", "text.test.v1"])
        assert result.exit_code == 0
        mock_rebuild.assert_called_once_with("text.test.v1")
        assert "Rebuilt index for space: text.test.v1" in result.output


def test_index_cmd_reindex_alias(temp_workspace: GeoMemory) -> None:
    runner = CliRunner()
    ws_path = str(temp_workspace.get_workspace_path())

    with patch("geomemory.cli.commands.reindex.reindex") as mock_reindex:
        result = runner.invoke(
            index_cmd,
            ["reindex", "-w", ws_path, "--provider", "onnx", "--model", "test-model"],
        )
        assert result.exit_code == 0
