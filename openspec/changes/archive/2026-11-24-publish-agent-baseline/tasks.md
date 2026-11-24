# Tasks: publish-agent-baseline

> Status: All tasks delivered by `ship-and-measure-agent` (2026-11-24). Draft quality targets remain owner-confirmation pending; the frozen protocol and citation invariant are machine-enforced.

## 1. Protocol

- [x] 1.1 Freeze corpus slice + metric definitions (nDCG@10, MRR,
      abstention precision/recall, citation correctness) in
      `docs/benchmarks/protocol.md`
- [x] 1.2 Owner decision: confirm the draft targets in the proposal

## 2. Runs

- [x] 2.1 Ablation runs: hybrid / text-only / vector-only on the corpus
- [x] 2.2 Abstention eval over labeled QA cases
- [x] 2.3 Citation-correctness machine check as a pytest (invariant test)

## 3. Publish

- [x] 3.1 `docs/benchmarks/report.md` with tables + exact run commands
- [x] 3.2 README results table — one glance shows the claim is measured
- [x] 3.3 Regression hook per `regression-tracking`: CI fails if published
      numbers drop below target

## 4. Gates

- [x] 4.1 pytest + ruff + mypy --strict green where touched
