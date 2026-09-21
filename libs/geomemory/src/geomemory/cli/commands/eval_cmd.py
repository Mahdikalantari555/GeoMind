"""geomemory eval command."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import click
import yaml

from geomemory.core.workspace import GeoMemory
from geomemory.eval.pipeline_stats import STATS_FIELDS, collect_stats, stats_to_json
from geomemory.eval.run_store import BaselineStore, RunStore

EVAL_ROOT = Path("geomemory-evals")
DATASETS_DIR = EVAL_ROOT / "datasets"
WORKSPACES_DIR = EVAL_ROOT / "workspaces"
RUNS_DIR = EVAL_ROOT / "runs"
CORPUS_DIR = EVAL_ROOT / "corpus"
BASELINES_DIR = EVAL_ROOT / "baselines"


@click.group()
def eval_cmd() -> None:
    """Eval framework commands."""


@eval_cmd.group("baseline")
def baseline_cmd() -> None:
    """Baseline management: set, get, and list pinned baselines."""


@baseline_cmd.command("set")
@click.argument("dataset")
@click.option("--runs-dir", type=click.Path(), default=None, help="Run store base directory")
@click.option("--baselines-dir", type=click.Path(), default=None, help="Baselines directory")
def baseline_set(dataset: str, runs_dir: str | None, baselines_dir: str | None) -> None:
    """Pin the newest run for *dataset* as the active baseline."""
    store = RunStore(runs_dir) if runs_dir else RunStore(RUNS_DIR)
    runs = store.list_runs(dataset)
    if not runs:
        raise click.ClickException(f"No runs found for dataset: {dataset}")
    latest = runs[0]  # already sorted newest first
    run_data = store.read_run(dataset, latest["timestamp"])
    metrics: dict[str, Any] = {}
    for bname, bdata in run_data.get("benchmarks", {}).items():
        metrics[bname] = bdata.get("metrics", {})
    bl_store = BaselineStore(baselines_dir) if baselines_dir else BaselineStore(BASELINES_DIR)
    bl_store.set(dataset, latest["timestamp"], latest["path"], metrics)
    click.echo(f"Baseline set for {dataset}: {latest['timestamp']}")
    click.echo(f"  path: {latest['path']}")


@baseline_cmd.command("get")
@click.argument("dataset")
@click.option("--baselines-dir", type=click.Path(), default=None, help="Baselines directory")
def baseline_get(dataset: str, baselines_dir: str | None) -> None:
    """Show the current baseline for *dataset*."""
    bl_store = BaselineStore(baselines_dir) if baselines_dir else BaselineStore(BASELINES_DIR)
    baseline = bl_store.get(dataset)
    if baseline is None:
        click.echo(f"No baseline set for dataset: {dataset}")
        return
    click.echo(f"Baseline for {dataset}:")
    click.echo(f"  timestamp: {baseline['timestamp']}")
    click.echo(f"  path: {baseline['path']}")
    for bname, bmetrics in baseline.get("metrics", {}).items():
        click.echo(f"  benchmark {bname} metrics:")
        for fam, vals in bmetrics.items():
            click.echo(f"    {fam}: {json.dumps(vals, sort_keys=True)}")


@baseline_cmd.command("list")
@click.option("--baselines-dir", type=click.Path(), default=None, help="Baselines directory")
def baseline_list(baselines_dir: str | None) -> None:
    """List all datasets with pinned baselines."""
    bl_store = BaselineStore(baselines_dir) if baselines_dir else BaselineStore(BASELINES_DIR)
    items = bl_store.list_datasets()
    if not items:
        click.echo("No baselines pinned.")
        return
    for item in items:
        click.echo(f"{item['dataset']}: {item['timestamp']}")


@eval_cmd.group("corpus")
def corpus_cmd() -> None:
    """Corpus registry commands."""


@corpus_cmd.command("list")
@click.option("--corpus-dir", type=click.Path(), default=None, help="Corpus root directory")
def corpus_list(corpus_dir: str | None) -> None:
    """Enumerate all benchmarks in the corpus, grouped by version."""
    from geomemory.eval.corpus import list_corpus_benchmarks  # noqa: local import

    root = Path(corpus_dir) if corpus_dir else CORPUS_DIR
    benchmarks = list_corpus_benchmarks(root)
    if not benchmarks:
        click.echo("No benchmarks in corpus.")
        return
    for entry in benchmarks:
        click.echo(f"{entry['version']}/{entry['name']} ({entry['path']})")


@eval_cmd.command("run")
@click.argument("benchmark_path", type=click.Path(exists=True))
@click.option("--workspace", "-w", type=click.Path(), default=".", help="Workspace path")
@click.option("--config", type=click.Path(), default=None, help="Benchmark config JSON")
@click.option("--dataset", default=None, help="Dataset name for run persistence")
@click.option("--runs-dir", type=click.Path(), default=None, help="Run store base directory")
@click.option("--stats-json", type=click.Path(), default=None, help="Stats JSON to attach to the run")
@click.option("--manifest-yaml", type=click.Path(), default=None, help="Dataset manifest YAML")
@click.option("--baseline", default=None, help="Dataset to auto-compare against its baseline")
@click.option("--threshold", default=None, type=float, help="Drift threshold (absolute delta)")
def run(
    benchmark_path: str,
    workspace: str,
    config: str | None,
    dataset: str | None,
    runs_dir: str | None,
    stats_json: str | None,
    manifest_yaml: str | None,
    baseline: str | None,
    threshold: float | None,
) -> None:
    """Run a benchmark from a JSONL file."""
    ws = GeoMemory.open(workspace)
    try:
        stats = _load_stats(stats_json) if stats_json else None
        manifest = _load_manifest(manifest_yaml) if manifest_yaml else None
        store = RunStore(runs_dir) if runs_dir else None
        result = ws.run_benchmark(
            benchmark_path,
            config,
            run_store=store,
            dataset=dataset,
            stats=stats,
            manifest=manifest,
        )
        click.echo(f"Benchmark: {result.name}")
        click.echo(f"  metrics: {result.metrics}")
        if store is not None and dataset is not None:
            click.echo(f"  artifacts: {RUNS_DIR / dataset}")

        if baseline is not None and store is not None:
            _run_baseline_compare(
                store, dataset, result.metrics, baseline, threshold,
                runs_dir,
            )
    finally:
        ws.close()


def _run_baseline_compare(
    store: RunStore,
    dataset: str,
    current_metrics: dict[str, Any],
    baseline_dataset: str,
    threshold: float | None,
    runs_dir: str | None,
) -> None:
    """Auto-compare the just-written run against the pinned baseline."""
    from geomemory.eval.regression import detect_drift, has_regression  # noqa: local import

    bl_store = BaselineStore(runs_dir) if runs_dir else BaselineStore(BASELINES_DIR)
    bp = bl_store.get(baseline_dataset)
    if bp is None:
        raise click.ClickException(f"No baseline pinned for dataset: {baseline_dataset}")

    # Read baseline run metrics from the run store
    base_run = store.read_run(baseline_dataset, bp["timestamp"])
    base_metrics: dict[str, Any] = {}
    for bname, bdata in base_run.get("benchmarks", {}).items():
        base_metrics[bname] = bdata.get("metrics", {})

    drift = detect_drift(
        base_metrics,
        current_metrics,
        threshold=threshold if threshold is not None else 0.05,
    )
    if has_regression(drift):
        click.echo("")
        click.echo("REGRESSION DETECTED:", err=True)
        for fam, metrics in drift.items():
            for mname, entry in metrics.items():
                if entry.get("regressed"):
                    click.echo(
                        f"  {f'{fam}.{mname}':<30} {entry['baseline']} -> {entry['current']} "
                        f"(delta {entry['delta']:+g})"
                    )
        raise click.exceptions.Exit(1)
    click.echo("  No regression detected (within threshold).")


@eval_cmd.command("compare")
@click.argument("run_a", type=click.Path())
@click.argument("run_b", type=click.Path())
@click.option("--dataset", default=None, help="Dataset name (used in CI output)")
@click.option("--threshold", default=None, type=float, help="Drift threshold (absolute delta)")
@click.option("--ci", is_flag=True, default=False, help="Emit CI-compatible JSON diff")
def compare(run_a: str, run_b: str, dataset: str | None, threshold: float | None, ci: bool) -> None:
    """Diff two persisted runs and exit non-zero on any difference."""
    path_a = Path(run_a)
    path_b = Path(run_b)
    if not path_a.is_dir():
        raise click.ClickException(f"Run directory not found: {path_a}")
    if not path_b.is_dir():
        raise click.ClickException(f"Run directory not found: {path_b}")

    diff = _compare_runs(path_a, path_b)
    thr = threshold if threshold is not None else 0.05

    if ci:
        from geomemory.eval.regression import (  # noqa: local import
            ci_json_to_string,
            detect_drift,
            has_regression,
            to_ci_json,
        )

        metrics_a: dict[str, Any] = {}
        metrics_b: dict[str, Any] = {}
        benchmarks: list[str] = []
        for fname in sorted(path_a.glob("*.json")):
            if fname.name == "stats.json":
                continue
            data = json.loads(fname.read_text(encoding="utf-8"))
            bname = data.get("name", fname.stem)
            benchmarks.append(bname)
            metrics_a[bname] = data.get("metrics", {})
        for fname in sorted(path_b.glob("*.json")):
            if fname.name == "stats.json":
                continue
            data = json.loads(fname.read_text(encoding="utf-8"))
            bname = data.get("name", fname.stem)
            if bname not in metrics_b:
                metrics_b[bname] = {}
            metrics_b[bname].update(data.get("metrics", {}))

        drifts: dict[str, Any] = {}
        for bname in benchmarks:
            drifts[bname] = detect_drift(
                metrics_a.get(bname, {}),
                metrics_b.get(bname, {}),
                threshold=thr,
            )

        out = to_ci_json(
            {
                "baseline_run": str(path_a),
                "current_run": str(path_b),
                "dataset": dataset or path_a.parent.name,
                "benchmarks": [{"name": b, "metrics": {}} for b in benchmarks],
                "drifts": drifts,
            },
            threshold=thr,
        )
        out["changed"] = diff["changed"]
        out["drifts"] = drifts
        click.echo(ci_json_to_string(out))
        ok = not has_regression(drifts) and not diff["changed"]
        if not ok:
            raise click.exceptions.Exit(1)
        return

    click.echo(json.dumps(diff, sort_keys=True, indent=2))
    _print_summary(diff)
    if diff["changed"]:
        raise click.exceptions.Exit(1)


@eval_cmd.command("stats")
@click.argument("dataset", type=click.Path())
@click.option("--runs-dir", type=click.Path(), default=None, help="Run store base directory")
def stats(dataset: str, runs_dir: str | None) -> None:
    """Ingest a dataset into a scratch workspace and emit pipeline statistics."""
    dataset_path = _resolve_dataset(dataset)
    dataset_name = dataset_path.name
    workspace_path = WORKSPACES_DIR / dataset_name
    workspace_path.parent.mkdir(parents=True, exist_ok=True)

    ws = _create_or_open_workspace(workspace_path)
    try:
        coll = _ensure_collection(ws, "eval")
        start = time.perf_counter()
        errors = _ingest_dataset(ws, dataset_path, coll.id)
        duration = time.perf_counter() - start
        if errors:
            raise click.ClickException(
                "Ingestion failed for " + ", ".join(sorted(errors))
            )
        stats_payload = collect_stats(ws.conn, ws.path, duration_seconds=duration)
        click.echo(stats_to_json(stats_payload))
        store = RunStore(runs_dir) if runs_dir else RunStore(RUNS_DIR)
        run_dir = store.write_stats_only(dataset_name, stats_payload)
        click.echo(f"  artifacts: {run_dir}")
    finally:
        ws.close()


@eval_cmd.command("rebuild")
@click.argument("dataset", type=click.Path())
@click.option("--runs-dir", type=click.Path(), default=None, help="Run store base directory")
def rebuild(dataset: str, runs_dir: str | None) -> None:
    """Delete and recreate a scratch workspace, re-ingest, and emit stats."""
    dataset_path = _resolve_dataset(dataset)
    dataset_name = dataset_path.name
    workspace_path = WORKSPACES_DIR / dataset_name

    # Sandbox isolation: never touch the user's real workspace.
    if workspace_path.exists():
        shutil.rmtree(workspace_path)
    workspace_path.parent.mkdir(parents=True, exist_ok=True)

    ws = GeoMemory.create(workspace_path)
    try:
        coll = ws.create_collection("eval")
        start = time.perf_counter()
        errors = _ingest_dataset(ws, dataset_path, coll.id)
        duration = time.perf_counter() - start
        if errors:
            raise click.ClickException(
                "Ingestion failed for " + ", ".join(sorted(errors))
            )
        stats_payload = collect_stats(ws.conn, ws.path, duration_seconds=duration)
        click.echo(stats_to_json(stats_payload))
        store = RunStore(runs_dir) if runs_dir else RunStore(RUNS_DIR)
        run_dir = store.write_stats_only(dataset_name, stats_payload)
        click.echo(f"  artifacts: {run_dir}")
    finally:
        ws.close()


def _resolve_dataset(dataset: str) -> Path:
    """Resolve a dataset name or path under ``geomemory-evals/datasets``."""
    candidate = Path(dataset)
    if candidate.is_dir():
        return candidate.resolve()
    if candidate.name == dataset and "/" not in dataset and "\\" not in dataset:
        direct = DATASETS_DIR / dataset
        if direct.is_dir():
            return direct.resolve()
    raise click.ClickException(f"Dataset not found: {dataset}")


def _create_or_open_workspace(path: Path) -> GeoMemory:
    if (path / ".geomemory").is_file():
        return GeoMemory.open(path)
    return GeoMemory.create(path)


def _ensure_collection(ws: GeoMemory, name: str) -> Any:
    for coll in ws.list_collections():
        if coll.name == name:
            return coll
    return ws.create_collection(name)


def _ingest_dataset(ws: GeoMemory, dataset_path: Path, collection_id: str) -> list[str]:
    """Ingest every source file in a dataset; return per-file errors."""
    errors: list[str] = []
    for source in sorted(_iter_sources(dataset_path)):
        try:
            ws.ingest(source, collection_id=collection_id)
        except Exception as exc:  # noqa: BLE001 - per-file errors are surfaced together
            errors.append(f"{source.name}: {exc}")
    return errors


def _iter_sources(dataset_path: Path) -> list[Path]:
    """Yield ingestible source files, skipping metadata YAML files."""
    sources: list[Path] = []
    for path in dataset_path.rglob("*"):
        if not path.is_file():
            continue
        if path.name in {"queries.yaml", "manifest.yaml"}:
            continue
        sources.append(path)
    return sources


def _load_stats(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [field for field in STATS_FIELDS if field not in data]
    if missing:
        raise click.ClickException(
            "Stats JSON missing fields: " + ", ".join(sorted(missing))
        )
    return data


def _load_manifest(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise click.ClickException(f"Manifest must be a mapping: {path}")
    return data


def _compare_runs(run_a: Path, run_b: Path) -> dict[str, Any]:
    """Return a machine-readable diff between two run directories."""
    stats_a = json.loads((run_a / "stats.json").read_text(encoding="utf-8"))
    stats_b = json.loads((run_b / "stats.json").read_text(encoding="utf-8"))
    stats_delta = {
        field: {"a": stats_a.get(field), "b": stats_b.get(field), "delta": _delta(stats_a.get(field), stats_b.get(field))}
        for field in STATS_FIELDS
        if stats_a.get(field) != stats_b.get(field)
    }

    rows_a = _load_benchmark_rows(run_a)
    rows_b = _load_benchmark_rows(run_b)
    query_diff: dict[str, Any] = {}
    for query in sorted(set(rows_a) | set(rows_b)):
        if query not in rows_a:
            query_diff[query] = {"status": "absent_in_a"}
            continue
        if query not in rows_b:
            query_diff[query] = {"status": "absent_in_b"}
            continue
        a_ids = set(rows_a[query].get("retrieved", []))
        b_ids = set(rows_b[query].get("retrieved", []))
        missing = sorted(a_ids - b_ids)
        new = sorted(b_ids - a_ids)
        if missing or new:
            query_diff[query] = {"missing_in_b": missing, "new_in_b": new}

    changed = bool(stats_delta or query_diff)
    return {
        "run_a": str(run_a),
        "run_b": str(run_b),
        "changed": changed,
        "stats_delta": stats_delta,
        "query_diff": query_diff,
    }


def _load_benchmark_rows(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Index per-query rows by query text across all benchmark JSON files."""
    rows: dict[str, dict[str, Any]] = {}
    for path in run_dir.glob("*.json"):
        if path.name == "stats.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("rows", []):
            query = row.get("query")
            if query:
                rows[query] = row
    return rows


def _delta(a: Any, b: Any) -> Any:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return b - a
    return None


def _print_summary(diff: dict[str, Any]) -> None:
    """Print a human-readable comparison summary."""
    if not diff["changed"]:
        click.echo("Runs are equivalent.")
        return
    click.echo("Runs differ.")
    for field, values in diff["stats_delta"].items():
        click.echo(f"  {field}: {values['a']} -> {values['b']} ({values['delta']:+g})")
    for query, values in diff["query_diff"].items():
        if "missing_in_b" in values:
            click.echo(f"  query {query!r}: missing in B: {', '.join(values['missing_in_b'])}")
        if "new_in_b" in values:
            click.echo(f"  query {query!r}: new in B: {', '.join(values['new_in_b'])}")
        if "status" in values:
            click.echo(f"  query {query!r}: {values['status']}")
