#!/usr/bin/env python3
"""Reproducible agent-baseline benchmark (change: ship-and-measure-agent).

Protocol (frozen in docs/benchmarks/protocol.md):
  corpus   — 5 golden fixtures, 5 retrieval queries, 3 QA queries
  seeds    — [42]; top_k — [10]
  retrieval— hybrid (RRF fusion), sparse (text-only), dense (vector-only)
  QA       — abstention confusion matrix + citation-resolution invariant

Runs fully offline. The QA "oracle-stub" regime monkeypatches the LLM backend
with a deterministic generator that cites the *real* top retrieved segment, so
citation correctness measures the citation/provenance pipeline, not a model.

Usage:
    python scripts/benchmark_agent_baseline.py --out docs/benchmarks
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from geomemory import GeoMemory
from geomemory.core.models import GenerationRequest, GenerationResult
from geomemory.eval.runner import BenchmarkRunner

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "libs" / "geomemory"
FIXTURES = LIB / "tests" / "golden" / "fixtures"
RETRIEVAL_BENCH = LIB / "benchmarks" / "retrieval" / "phase1_benchmark.jsonl"
QA_BENCH = LIB / "benchmarks" / "qa" / "phase1_benchmark.jsonl"

SEEDS = [42]
TOP_KS = [10]
MODES = ("hybrid", "sparse", "dense")
ABSTENTION_THRESHOLD = 0.55  # normalized relevance [0,1]; below → abstain
TOLERANCE = 0.02  # published-number regression tolerance


# ── Corpus helpers (mirror libs/geomemory/scripts/run_phase1_benchmark.py) ──


def _resolve_gold_ids(conn: sqlite3.Connection, substring: str) -> list[str]:
    rows = conn.execute(
        "SELECT id FROM segment WHERE instr(text, ?) > 0 LIMIT 5", (substring,)
    ).fetchall()
    return [str(r["id"]) for r in rows]


def _resolve_benchmark(path: Path, conn: sqlite3.Connection, tmpdir: Path) -> Path:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        substring = item.get("metadata", {}).get("gold_substring")
        if substring:
            item["gold_ids"] = _resolve_gold_ids(conn, substring)
        out.append(json.dumps(item, ensure_ascii=False))
    target = tmpdir / f"{path.stem}.resolved.jsonl"
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    return target


def _ingest_fixtures(ws: GeoMemory) -> None:
    col = ws.create_collection("phase1_golden")
    for fixture in sorted(FIXTURES.iterdir()):
        if fixture.suffix in (".pdf", ".docx"):
            continue
        ws.ingest(fixture, collection_id=col.id)


# ── Deterministic QA stub (no model, no network) ────────────────────────────


class OracleStubBackend:
    """Cite the real top retrieved segment; never invent a source."""

    model_id = "oracle-stub-v0"

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not request.context:
            return GenerationResult(
                text="not found in selected sources",
                prompt_hash="",
                model_id=self.model_id,
                abstained=True,
            )
        return GenerationResult(
            text="Grounded answer [1].",
            prompt_hash="",
            model_id=self.model_id,
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


def _stub_factory(settings: Any) -> tuple[OracleStubBackend, int]:
    return OracleStubBackend(), 2000


# ── Metrics ──────────────────────────────────────────────────────────────────


def _retrieval_ablation(ws: GeoMemory, bench_path: Path) -> dict[str, dict[str, float]]:
    runner = BenchmarkRunner(ws)
    results: dict[str, dict[str, float]] = {}
    for mode in MODES:
        cfg = json.dumps({"seeds": SEEDS, "top_k_values": TOP_KS, "mode": mode})
        result = runner.run(str(bench_path), cfg)
        results[mode] = {
            "ndcg@10": result.metrics["retrieval"]["ndcg@10"],
            "mrr@10": result.metrics["retrieval"]["mrr@10"],
        }
    return results


def _qa_regimes(ws: GeoMemory, bench_path: Path) -> dict[str, Any]:
    from geomemory.core.models import QAResult

    items = [json.loads(line) for line in bench_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    confusion: dict[str, int] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for item in items:
        expected = bool(item["expected_abstain"])
        try:
            answer: QAResult = ws.ask(item["query"])
        except Exception:  # noqa: BLE001 — an unavailable backend is an abstention
            answer = QAResult(text="not found in selected sources", abstained=True, model="none")
        predicted = bool(answer.abstained)
        key = ("tp" if expected else "fp") if predicted else ("fn" if expected else "tn")
        confusion[key] += 1
    total = sum(confusion.values())
    precision = confusion["tp"] / (confusion["tp"] + confusion["fp"]) if (confusion["tp"] + confusion["fp"]) else 0.0
    answer_recall = confusion["tn"] / (confusion["tn"] + confusion["fp"]) if (confusion["tn"] + confusion["fp"]) else 0.0

    # Citation correctness = structural resolution: every citation emitted by
    # the stub must resolve to a real segment with a non-empty locator. This is
    # the provenance-chain invariant (answer → citation → segment), independent
    # of which source the retriever ranked first.
    with patch("geomemory.qa.backend_factory.build_llm_backend", _stub_factory):
        total_citations = 0
        resolved = 0
        for item in items:
            answer = ws.ask(item["query"])
            for citation in answer.citations:
                total_citations += 1
                row = ws.conn.execute(
                    "SELECT 1 FROM segment WHERE id = ? LIMIT 1", (citation.segment_id,)
                ).fetchone()
                if row is not None and bool(citation.locator):
                    resolved += 1
    return {
        "no_backend": {
            "confusion": confusion,
            "items": total,
            "abstention_precision": precision,
            "answer_recall": answer_recall,
            "note": "No LLM backend configured in this environment; the system abstains on every answerable item. This is the honest degraded-mode measurement.",
        },
        "oracle_stub": {
            "citations_emitted": total_citations,
            "citations_resolved": resolved,
            "citation_resolution": resolved / total_citations if total_citations else 0.0,
            "note": "Deterministic stub cites the real top retrieved segment; measures the citation/provenance pipeline, not model quality.",
        },
    }


def run_benchmark(out_dir: Path) -> dict[str, Any]:
    tmp = tempfile.TemporaryDirectory(prefix="geomind-baseline-")
    ws = GeoMemory.create(Path(tmp.name) / "ws")
    try:
        _ingest_fixtures(ws)
        bench = _resolve_benchmark(RETRIEVAL_BENCH, ws.conn, Path(tmp.name))
        qa_bench = _resolve_benchmark(QA_BENCH, ws.conn, Path(tmp.name))
        report: dict[str, Any] = {
            "protocol": {
                "corpus": "libs/geomemory/tests/golden/fixtures (5 text fixtures)",
                "retrieval_items": 5,
                "qa_items": 3,
                "seeds": SEEDS,
                "top_k": TOP_KS,
                "abstention_threshold": ABSTENTION_THRESHOLD,
                "modes": list(MODES),
                "citation_definition": "fraction of emitted citations whose segment_id resolves to an existing segment with a non-empty locator",
                "baseline_targets": "draft (owner to confirm): hybrid >= +10% nDCG@10 over text-only; abstention precision >= 0.95; answer recall >= 0.90; citation resolution = 1.0",
            },
            "retrieval": _retrieval_ablation(ws, bench),
            "qa": _qa_regimes(ws, qa_bench),
        }
    finally:
        ws.close()
        tmp.cleanup()

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "benchmarks")
    args = parser.parse_args()
    report = run_benchmark(args.out)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
