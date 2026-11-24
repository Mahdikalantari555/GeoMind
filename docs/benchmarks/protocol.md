# Agent baseline — frozen protocol

> Change: `ship-and-measure-agent`. This protocol is the contract for the
> numbers in `report.md`. Do not change the corpus, seeds or metric definitions
> without re-running `python scripts/benchmark_agent_baseline.py` and updating
> the report in the same commit.

## Corpus slice

- **Fixture corpus:** `libs/geomemory/tests/golden/fixtures/` — the five text
  fixtures (`analysis.ipynb`, `ndvi.py`, `rs_notes.md`, `flood_report.pdf`,
  `landcover.docx`). The two optional binary formats are skipped, matching the
  existing `run_phase1_benchmark.py` harness. One collection, `phase1_golden`.
- **Retrieval slice:** `libs/geomemory/benchmarks/retrieval/phase1_benchmark.jsonl`
  (5 queries). Gold segment ids are resolved at run time by substring match on
  `metadata.gold_substring` (same rule as the Phase 1 harness).
- **QA slice:** `libs/geomemory/benchmarks/qa/phase1_benchmark.jsonl` (3 queries:
  2 answerable, 1 labelled `expected_abstain`).
- **Sample size caveat:** 5 retrieval / 3 QA items. These numbers establish a
  reproducible *regression baseline*, not a statistically stable quality
  estimate. The draft quality targets await a larger labelled slice.

## Seeds and configuration

- `seeds = [42]` (recorded in `BenchmarkConfig`; the hashing path is
  deterministic for this corpus).
- `top_k_values = [10]`; reported metrics are `@10`.
- Retrieval modes: `hybrid` (RRF fusion), `sparse` (text-only FTS), `dense`
  (vector-only). `BenchmarkRunner` and production ingestion/search code are
  used unchanged.
- Abstention threshold (for the labelled confusion matrix): normalized
  relevance `< 0.55` → abstain.
- QA stub: `OracleStubBackend` emits `[1]` citing `request.context[0]` — the
  real top retrieved segment — or abstains when no context is packed. It is a
  **deterministic stand-in for the LLM**, not a model-quality measurement. No
  network, model download or API key is required.

## Metric definitions

| Metric | Definition |
|---|---|
| nDCG@10 | Normalized discounted cumulative gain over gold segments at rank 10 (`geomemory.eval.retrieval_metrics.ndcg_at_k`). |
| MRR@10 | Mean reciprocal rank of the first gold segment in the top 10 (`mrr_at_k`). |
| Abstention precision | `TP / (TP + FP)` where positive = "should abstain" (labelled `expected_abstain`) and prediction = run's `abstained` flag. |
| Answer recall | `TN / (TN + FP)` — of the items that should be answered, the fraction actually answered. |
| Citation resolution | Fraction of emitted citations whose `segment_id` resolves to an existing row in `segment` **and** whose `locator` is non-empty. Machine-enforced invariant: target 1.0. |

## Regeneration

```bash
conda run -n geo python scripts/benchmark_agent_baseline.py --out docs/benchmarks
```

The script writes `results.json`, which is read by
`libs/geomemory/tests/eval/test_published_baseline.py`. That pytest re-runs the
benchmark and fails if any published retrieval metric moves by more than
`±0.02` or if citation resolution drops below 1.0 — this is the regression
hook for `regression-tracking`.
