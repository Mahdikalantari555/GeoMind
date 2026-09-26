"""Unit tests for geomemory eval CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from geomemory.cli.main import cli
from geomemory.eval.pipeline_stats import STATS_FIELDS


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_eval_corpus_list(runner: CliRunner, tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()

    # Empty corpus
    res_empty = runner.invoke(cli, ["eval", "corpus", "list", "--corpus-dir", str(corpus_dir)])
    assert res_empty.exit_code == 0
    assert "No benchmarks in corpus" in res_empty.output

    # Populated corpus
    v1_dir = corpus_dir / "v1"
    v1_dir.mkdir(parents=True)
    (v1_dir / "bench1.jsonl").write_text('{"query": "test"}\n')
    res_pop = runner.invoke(cli, ["eval", "corpus", "list", "--corpus-dir", str(corpus_dir)])
    assert res_pop.exit_code == 0
    assert "v1/bench1" in res_pop.output


def test_eval_baseline_lifecycle(runner: CliRunner, tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    bl_dir = tmp_path / "baselines"
    bl_dir.mkdir()

    # Create synthetic run in runs_dir
    run_time = "2026-09-01T12-00-00Z"
    ds_run = runs_dir / "ds1" / run_time
    ds_run.mkdir(parents=True)
    bench_data = {
        "name": "b1",
        "metrics": {"retrieval": {"mrr": 0.85, "ndcg": 0.90}},
    }
    (ds_run / "b1.json").write_text(json.dumps(bench_data))
    (ds_run / "stats.json").write_text(json.dumps({f: 0 for f in STATS_FIELDS}))

    # Set baseline
    res_set = runner.invoke(
        cli,
        ["eval", "baseline", "set", "ds1", "--runs-dir", str(runs_dir), "--baselines-dir", str(bl_dir)],
    )
    assert res_set.exit_code == 0
    assert "Baseline set for ds1" in res_set.output

    # Get baseline
    res_get = runner.invoke(cli, ["eval", "baseline", "get", "ds1", "--baselines-dir", str(bl_dir)])
    assert res_get.exit_code == 0
    assert "Baseline for ds1" in res_get.output
    assert "retrieval:" in res_get.output

    # List baselines
    res_list = runner.invoke(cli, ["eval", "baseline", "list", "--baselines-dir", str(bl_dir)])
    assert res_list.exit_code == 0
    assert "ds1:" in res_list.output


def test_eval_compare_equivalent_and_different(runner: CliRunner, tmp_path: Path) -> None:
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    run_a.mkdir()
    run_b.mkdir()

    stats = {f: 10 for f in STATS_FIELDS}
    (run_a / "stats.json").write_text(json.dumps(stats))
    (run_b / "stats.json").write_text(json.dumps(stats))

    row_data = {
        "name": "b1",
        "rows": [{"query": "ndvi", "retrieved": ["seg1", "seg2"]}],
    }
    (run_a / "b1.json").write_text(json.dumps(row_data))
    (run_b / "b1.json").write_text(json.dumps(row_data))

    # Compare identical
    res_same = runner.invoke(cli, ["eval", "compare", str(run_a), str(run_b)])
    assert res_same.exit_code == 0
    assert "Runs are equivalent" in res_same.output

    # Modify run_b to cause differences
    stats_b = dict(stats)
    stats_b["chunks"] = 25
    (run_b / "stats.json").write_text(json.dumps(stats_b))
    row_data_b = {
        "name": "b1",
        "rows": [{"query": "ndvi", "retrieved": ["seg1", "seg3"]}],
    }
    (run_b / "b1.json").write_text(json.dumps(row_data_b))

    res_diff = runner.invoke(cli, ["eval", "compare", str(run_a), str(run_b)])
    assert res_diff.exit_code != 0
    assert "Runs differ" in res_diff.output
    assert "chunks:" in res_diff.output

    # CI mode
    res_ci = runner.invoke(cli, ["eval", "compare", str(run_a), str(run_b), "--ci"])
    assert res_ci.exit_code != 0


def test_eval_compare_missing_dirs(runner: CliRunner, tmp_path: Path) -> None:
    res = runner.invoke(cli, ["eval", "compare", str(tmp_path / "no_a"), str(tmp_path / "no_b")])
    assert res.exit_code != 0
    assert "not found" in res.output


def test_eval_stats_and_rebuild(runner: CliRunner, tmp_path: Path) -> None:
    ds_dir = tmp_path / "my_dataset"
    ds_dir.mkdir()
    (ds_dir / "sample.md").write_text("# Test Document\nVegetation monitoring.\n")
    (ds_dir / "manifest.yaml").write_text("name: my_dataset\n")

    runs_dir = tmp_path / "eval_runs"

    with patch("geomemory.cli.commands.eval_cmd.WORKSPACES_DIR", tmp_path / "ws"):
        # Test stats command
        res_stats = runner.invoke(cli, ["eval", "stats", str(ds_dir), "--runs-dir", str(runs_dir)])
        assert res_stats.exit_code == 0
        assert "chunks" in res_stats.output

        # Test rebuild command
        res_rebuild = runner.invoke(cli, ["eval", "rebuild", str(ds_dir), "--runs-dir", str(runs_dir)])
        assert res_rebuild.exit_code == 0
        assert "chunks" in res_rebuild.output


def test_eval_run_command_mocked(runner: CliRunner, tmp_path: Path) -> None:
    bench_file = tmp_path / "bench.jsonl"
    bench_file.write_text('{"query": "ndvi"}\n')
    ws_dir = tmp_path / "ws"
    runner.invoke(cli, ["init", str(ws_dir)])

    mock_res = MagicMock()
    mock_res.name = "bench1"
    mock_res.metrics = {"precision": 1.0}

    with patch("geomemory.core.workspace.GeoMemory.run_benchmark", return_value=mock_res):
        res = runner.invoke(cli, ["eval", "run", str(bench_file), "-w", str(ws_dir)])
        assert res.exit_code == 0
        assert "Benchmark: bench1" in res.output
        assert "precision" in res.output
