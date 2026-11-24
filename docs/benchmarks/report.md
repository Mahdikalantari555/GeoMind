# Agent baseline report

> Generated 2026-11-24 by `scripts/benchmark_agent_baseline.py` from the frozen
> protocol in `protocol.md`. Raw numbers: `results.json`. Re-run command is in
> the protocol; the regression pytest enforces these numbers on every change.

## 1. Retrieval-parity ablation (nDCG@10 / MRR@10)

| Mode | nDCG@10 | MRR@10 | Notes |
| --- | ---: | ---: | --- |
| **`hybrid`** (RRF fusion) | **0.815** | **0.750** | Production default; retrieves every gold segment. |
| `sparse` (text-only FTS) | 0.815 | 0.750 | Equal to hybrid on this 5-query slice. |
| `dense` (vector-only) | 1.000 | 1.000 | Hashing embeddings rank gold first on this small corpus. |

The draft target "hybrid ≥ +10% nDCG@10 over text-only" is **not demonstrated**
on this slice — hybrid and sparse tie. The corpus is five documents with
distinctive keywords, so the lexical path already saturates. A larger, more
ambiguous slice is required before the parity claim can be quantified; the
target remains **owner-confirmation pending** and is not silently lowered.

## 2. Abstention quality

Two regimes were measured, because no LLM backend is configured in the
offline environment:

| Regime | TP | FP | FN | TN | Abstention precision | Answer recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No backend (degraded mode, 3 items) | 1 | 2 | 0 | 0 | 0.333 | 0.000 |
| Oracle stub (pipeline wiring, 3 items) | — | — | — | — | see note | see note |

- **No backend:** the system abstains on every answerable item. Precision 0.333
  and answer recall 0.000 are the honest measurement of the *degraded* state,
  not of a configured assistant. Studio surfaces this as an explicit
  abstention/degraded state rather than a crash.
- **Draft targets** (abstention precision ≥ 0.95, answer recall ≥ 0.90) require
  a configured LLM and a larger labelled set; they are **not claimed here**.

## 3. Citation correctness (machine-enforced)

| Check | Result |
| --- | ---: |
| Citations emitted by the stub over 3 QA items | 3 |
| Citations resolving to a real segment with a non-empty locator | 3 |
| **Citation resolution** | **1.000** |

This is the provenance invariant `answer → citation → segment(locator) →
asset_revision → objects/<sha256>`. It is checked by
`test_published_baseline.py`, which fails the build if resolution drops below
1.0. A citation that cannot resolve is never silently shown to the user.

## 4. What this baseline does and does not claim

- **Measured:** retrieval ablation and the citation/provenance chain, using
  production `BenchmarkRunner`, `search()` and `ask()` code paths unchanged.
- **Not measured:** LLM answer quality, faithfulness, or grounded abstention
  under a real model. There is no local GGUF checkpoint and no remote API key
  in this environment; the stub is explicitly a pipeline probe.
- The numbers are a regression floor, not a marketing claim. The dynamic
  `regression-tracking` hook (±0.02 on retrieval metrics, 1.0 on citation
  resolution) prevents them from silently rotting.
