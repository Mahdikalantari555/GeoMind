# Tasks: publish-agent-baseline

## 1. Protocol

- [ ] 1.1 Freeze corpus slice + metric definitions (nDCG@10, MRR,
      abstention precision/recall, citation correctness) in
      `docs/benchmarks/protocol.md`
- [ ] 1.2 Owner decision: confirm the draft targets in the proposal

## 2. Runs

- [ ] 2.1 Ablation runs: hybrid / text-only / vector-only on the corpus
- [ ] 2.2 Abstention eval over labeled QA cases
- [ ] 2.3 Citation-correctness machine check as a pytest (invariant test)

## 3. Publish

- [ ] 3.1 `docs/benchmarks/report.md` with tables + exact run commands
- [ ] 3.2 README results table — one glance shows the claim is measured
- [ ] 3.3 Regression hook per `regression-tracking`: CI fails if published
      numbers drop below target

## 4. Gates

- [ ] 4.1 pytest + ruff + mypy --strict green where touched
