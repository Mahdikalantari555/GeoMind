"""Unit tests for GeoMemory CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from geomemory.cli.main import cli
from geomemory.core.models import Asset, AssetDetail, AssetRevision, Segment


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_chat_command(runner: CliRunner, tmp_path: Path) -> None:
    ws_dir = tmp_path / "ws"
    runner.invoke(cli, ["init", str(ws_dir)])

    mock_answer = MagicMock()
    mock_answer.text = "NDVI is high"
    mock_answer.abstained = True
    mock_answer.abstention_reason = "Low confidence"
    mock_citation = MagicMock()
    mock_citation.locator = "doc.md#seg1"
    mock_answer.citations = [mock_citation]

    with patch("geomemory.core.workspace.GeoMemory.ask", return_value=mock_answer):
        result = runner.invoke(cli, ["chat", "-w", str(ws_dir)], input="What is NDVI?\nexit\n")
        assert result.exit_code == 0
        assert "GeoMemory: NDVI is high" in result.output
        assert "(abstained: Low confidence)" in result.output
        assert "[cite] doc.md#seg1" in result.output


def test_cli_inspect_command(runner: CliRunner, tmp_path: Path) -> None:
    ws_dir = tmp_path / "ws"
    runner.invoke(cli, ["init", str(ws_dir)])

    asset = Asset(
        id="asset-1",
        collection_id="col-1",
        kind="document",
        title="Field Report",
        current_revision_id="rev-1",
    )
    rev = AssetRevision(
        id="rev-1",
        asset_id="asset-1",
        hash="a" * 64,
        size_bytes=120,
        mime_type="text/markdown",
    )
    seg = Segment(
        id="seg-1",
        revision_id="rev-1",
        segment_type="paragraph",
        text="Sample segment content",
        locator={"page": 1},
    )
    mock_detail = AssetDetail(asset=asset, revision=rev, segments=[seg])

    with patch("geomemory.core.workspace.GeoMemory.inspect", return_value=mock_detail):
        result = runner.invoke(cli, ["inspect", "asset-1", "-w", str(ws_dir)])
        assert result.exit_code == 0
        assert "Asset: asset-1" in result.output
        assert "kind: document" in result.output
        assert "title: Field Report" in result.output
        assert f"hash: {'a'*64}" in result.output
        assert "segments: 1" in result.output
        assert "[paragraph] Sample segment content" in result.output


def test_cli_reindex_command(runner: CliRunner, tmp_path: Path) -> None:
    ws_dir = tmp_path / "ws"
    runner.invoke(cli, ["init", str(ws_dir)])

    # Test with legacy indexes dir present and force flag
    idx_dir = ws_dir / "indexes" / "text.st.test"
    idx_dir.mkdir(parents=True)
    (idx_dir / "manifest.json").write_text('{"model_id": "sentence-transformers/all-MiniLM-L6-v2"}')

    with patch("geomemory.core.workspace.GeoMemory.rebuild_index", return_value=None):
        result = runner.invoke(cli, ["reindex", "-w", str(ws_dir), "--force"])
        assert result.exit_code == 0
        assert "Reindexed segments into the target space" in result.output


def test_cli_reindex_no_legacy_no_force(runner: CliRunner, tmp_path: Path) -> None:
    ws_dir = tmp_path / "ws"
    runner.invoke(cli, ["init", str(ws_dir)])

    result = runner.invoke(cli, ["reindex", "-w", str(ws_dir), "--no-force"])
    assert result.exit_code == 0
    assert "No legacy txtai/ST markers found" in result.output


def test_cli_app_missing_dashboard(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(cli, ["app", "-w", str(tmp_path)])
    assert result.exit_code != 0
    assert "dashboard not found" in result.output


def test_cli_app_success_mocked(runner: CliRunner, tmp_path: Path) -> None:
    mock_stcli = MagicMock()
    with (
        patch.dict(sys.modules, {"streamlit.web": MagicMock(cli=mock_stcli)}),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        result = runner.invoke(cli, ["app", "-w", str(tmp_path)])
        assert result.exit_code == 0
        mock_stcli.main.assert_called_once()


def test_cli_feedback_commands(runner: CliRunner, tmp_path: Path) -> None:
    ws_dir = tmp_path / "ws"
    runner.invoke(cli, ["init", str(ws_dir)])

    mock_item = MagicMock()
    mock_item.id = "fb-1"
    mock_item.task_type = "qa_eval"
    mock_item.review_state = "pending"

    # review with items
    with patch("geomemory.core.workspace.GeoMemory.get_review_queue", return_value=[mock_item]):
        res_review = runner.invoke(cli, ["feedback", "review", "-w", str(ws_dir)])
        assert res_review.exit_code == 0
        assert "fb-1 [qa_eval] state=pending" in res_review.output

    # export success
    with patch("geomemory.core.workspace.GeoMemory.export_dataset", return_value="/tmp/dataset.json"):
        res_export = runner.invoke(
            cli,
            ["feedback", "export", "-w", str(ws_dir), "--type", "qa_eval", "--output", str(tmp_path)],
        )
        assert res_export.exit_code == 0
        assert "Exported dataset to /tmp/dataset.json" in res_export.output


def test_cli_eval_commands(runner: CliRunner, tmp_path: Path) -> None:
    bl_dir = tmp_path / "baselines"
    bl_dir.mkdir()

    # baseline list empty
    res_list = runner.invoke(cli, ["eval", "baseline", "list", "--baselines-dir", str(bl_dir)])
    assert res_list.exit_code == 0
    assert "No baselines pinned" in res_list.output

    # baseline get missing
    res_get = runner.invoke(cli, ["eval", "baseline", "get", "dataset1", "--baselines-dir", str(bl_dir)])
    assert res_get.exit_code == 0
    assert "No baseline set for dataset: dataset1" in res_get.output

    # baseline set when no runs exist raises
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    res_set = runner.invoke(
        cli,
        ["eval", "baseline", "set", "dataset1", "--runs-dir", str(runs_dir), "--baselines-dir", str(bl_dir)],
    )
    assert res_set.exit_code != 0
    assert "No runs found" in res_set.output
