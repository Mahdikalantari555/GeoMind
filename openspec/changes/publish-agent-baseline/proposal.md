# Proposal: publish-agent-baseline

## Why

The spine locked on 2026-11-21 is the **data-sovereign agent**: answers
cite or abstain, data never leaves the machine, feedback becomes training.
That identity is currently a *claim*. The delivered capabilities
`benchmark-corpus` and `retrieval-parity` exist, but no published numbers
back the product story — an external audit flagged exactly this ("claims
should become numbers"). This change turns the identity into measurements;
it is the end criterion for the spine.

## What Changes

- Run the benchmark corpus end-to-end and freeze a repeatable protocol
  (corpus slice, seeds, metric definitions).
- Publish a retrieval-parity ablation table — hybrid vs text-only vs
  vector-only (nDCG@10, MRR) — in `docs/benchmarks/report.md`.
- Publish abstention quality: precision when abstaining, recall when
  answering, over labeled QA cases.
- Machine-check citation correctness (every citation resolves to a real
  segment with a valid locator) — target 100%, enforced as a pytest.
- Record results in README (one table) and wire a regression hook
  (`regression-tracking`) so the numbers cannot silently rot.

## Draft targets (owner to confirm)

- retrieval-parity: hybrid ≥ +10% nDCG@10 over the text-only baseline on
  the corpus slice.
- abstention precision ≥ 0.95; answer recall ≥ 0.90.
- citation correctness = 100% (machine-enforced invariant).

## Impact

- Specs: `benchmark-corpus`, `retrieval-parity`, `regression-tracking`
  (ADDED requirements: published report + CI regression hook).
- Docs: new `docs/benchmarks/` (protocol + report); README results table.
- No app/lib behavior change beyond evaluation tooling and one CI job.
