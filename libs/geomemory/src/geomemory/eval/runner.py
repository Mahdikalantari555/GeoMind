"""Benchmark runner: executes retrieval and QA benchmarks against a workspace."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from geomemory.core.models import BenchmarkConfig, BenchmarkResult
from geomemory.eval.benchmark import BenchmarkItem, load_benchmark
from geomemory.eval.qa_metrics import (
    abstention_accuracy,
    citation_correctness,
    faithfulness_proxy,
)
from geomemory.eval.reporter import markdown_report
from geomemory.eval.retrieval_metrics import mrr_at_k, ndcg_at_k, precision_at_k, recall_at_k


class BenchmarkRunner:
    """Runs a benchmark JSONL against a ``GeoMemory`` workspace."""

    def __init__(self, workspace: Any) -> None:
        """Wrap a workspace exposing ``search()`` and ``ask()``."""
        self.workspace = workspace

    def run(
        self,
        benchmark_path: str,
        config: str | None = None,
        *,
        run_store: Any | None = None,
        dataset: str | None = None,
        stats: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Execute every benchmark item and aggregate metrics.

        ``config`` is a JSON file path or raw JSON string. Retrieval items are
        scored against ``gold_ids``; QA items are scored on abstention,
        citation correctness, and faithfulness.

        When ``run_store`` is provided, per-query rows are persisted alongside
        the aggregated metrics under ``runs/<dataset>/<timestamp>/``. The
        production ingestion/retrieval/QA code paths are used unchanged.
        """
        bench = load_benchmark(benchmark_path)
        cfg = self._load_config(config)
        self._check_top_k(cfg)

        retrieval_rows: list[dict[str, float]] = []
        qa_rows: list[dict[str, float]] = []
        retrieval_latencies: list[int] = []
        qa_latencies: list[int] = []
        per_query_rows: list[dict[str, Any]] = []

        for item in bench:
            if item.gold_ids:
                row, latency, per_row = self._run_retrieval_item(item, cfg)
                retrieval_rows.append(row)
                retrieval_latencies.append(latency)
                per_query_rows.append(per_row)
            if item.reference_answer or item.expected_abstain:
                row, latency, per_row = self._run_qa_item(item)
                qa_rows.append(row)
                qa_latencies.append(latency)
                per_query_rows.append(per_row)

        metrics: dict[str, dict[str, float]] = {
            "retrieval": self._aggregate_retrieval(retrieval_rows, cfg),
            "qa": self._aggregate_qa(qa_rows),
            "latency_ms": {
                "retrieval_avg": _avg(retrieval_latencies),
                "qa_avg": _avg(qa_latencies),
            },
        }
        result = BenchmarkResult(
            name=bench.name,
            metrics=metrics,
            report=markdown_report(bench.name, metrics),
            config=cfg,
        )

        if run_store is not None and dataset is not None:
            run_store.write_run(
                dataset=dataset,
                benchmark=bench.name,
                stats=stats or {},
                rows=per_query_rows,
                config=cfg.model_dump(),
                name=bench.name,
                metrics=metrics,
                manifest=manifest,
            )
        return result

    def _run_retrieval_item(
        self, item: BenchmarkItem, cfg: BenchmarkConfig
    ) -> tuple[dict[str, float], int, dict[str, Any]]:
        start = time.perf_counter()
        result = self.workspace.search(item.query, mode=cfg.mode, top_k=max(cfg.top_k_values))
        latency = int((time.perf_counter() - start) * 1000)
        retrieved = [hit.id for hit in result.hits]
        row: dict[str, float] = {}
        for k in cfg.top_k_values:
            row[f"recall@{k}"] = recall_at_k(item.gold_ids, retrieved, k)
            row[f"precision@{k}"] = precision_at_k(item.gold_ids, retrieved, k)
            row[f"mrr@{k}"] = mrr_at_k(item.gold_ids, retrieved, k)
            row[f"ndcg@{k}"] = ndcg_at_k(item.gold_ids, retrieved, k)
        per_row = {
            "query": item.query,
            "retrieved": retrieved,
            "scores": [float(hit.score) for hit in result.hits],
            "metadata": {
                "gold_ids": list(item.gold_ids),
                "mode": cfg.mode,
                "top_k_values": list(cfg.top_k_values),
                "latency_ms": latency,
                "retrieval_run_id": getattr(result, "retrieval_run_id", None),
            },
            "response": None,
        }
        return row, latency, per_row

    def _run_qa_item(self, item: BenchmarkItem) -> tuple[dict[str, float], int, dict[str, Any]]:
        start = time.perf_counter()
        result = self.workspace.ask(item.query)
        latency = int((time.perf_counter() - start) * 1000)
        context_ids = [hit.id for hit in result.sources]
        row = {
            "abstained": float(result.abstained),
            "abstention_accuracy": float(
                abstention_accuracy([result.abstained], [item.expected_abstain])
            ),
            "citation_correctness": citation_correctness(result.citations, item.gold_ids),
            "faithfulness_proxy": faithfulness_proxy(
                result.text, context_ids, item.gold_ids or None
            ),
        }
        per_row = {
            "query": item.query,
            "retrieved": context_ids,
            "scores": [float(hit.score) for hit in result.sources],
            "metadata": {
                "gold_ids": list(item.gold_ids),
                "reference_answer": item.reference_answer,
                "expected_abstain": bool(item.expected_abstain),
                "latency_ms": latency,
                "retrieval_run_id": getattr(result, "retrieval_run_id", None),
            },
            "response": result.text,
        }
        return row, latency, per_row

    @staticmethod
    def _aggregate_retrieval(rows: list[dict[str, float]], cfg: BenchmarkConfig) -> dict[str, float]:
        out: dict[str, float] = {}
        for k in cfg.top_k_values:
            for metric in ("recall", "precision", "mrr", "ndcg"):
                key = f"{metric}@{k}"
                values = [r[key] for r in rows if key in r]
                out[key] = _avg(values)
        return out

    @staticmethod
    def _aggregate_qa(rows: list[dict[str, float]]) -> dict[str, float]:
        if not rows:
            return {}
        return {
            "abstention_accuracy": _avg([r["abstention_accuracy"] for r in rows]),
            "citation_correctness": _avg([r["citation_correctness"] for r in rows]),
            "faithfulness_proxy": _avg([r["faithfulness_proxy"] for r in rows]),
            "abstain_rate": _avg([r["abstained"] for r in rows]),
        }

    @staticmethod
    def _load_config(config: str | None) -> BenchmarkConfig:
        if config is None:
            return BenchmarkConfig()
        config = config.strip()
        if config.startswith("{"):
            data = json.loads(config)
        else:
            path = Path(config)
            if not path.is_file():
                raise FileNotFoundError(f"Config file not found: {path}")
            data = json.loads(path.read_text(encoding="utf-8"))
        return BenchmarkConfig(**data)

    @staticmethod
    def _check_top_k(cfg: BenchmarkConfig) -> None:
        if not cfg.top_k_values:
            raise ValueError("top_k_values must not be empty")
        for k in cfg.top_k_values:
            if k < 1:
                raise ValueError(f"top_k must be >= 1, got {k}")


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
