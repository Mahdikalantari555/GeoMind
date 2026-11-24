# regression-tracking — Spec Delta

## ADDED Requirements

### Requirement: Published baseline regression hook
The project SHALL publish a repeatable report at `docs/benchmarks/report.md`
with a frozen protocol, a retrieval-parity ablation (nDCG@10/MRR@10),
abstention precision/recall and a machine-checked citation-correctness
invariant. A CI job SHALL re-run the protocol and fail when a published
retrieval metric moves beyond the frozen tolerance or citation resolution
drops below 1.0. The README SHALL carry a summary results table.

#### Scenario: Published numbers cannot rot
- **WHEN** a change alters retrieval quality beyond ±0.02 on any published mode or breaks citation resolution
- **THEN** the benchmark CI job fails and the report must be regenerated in the same change

#### Scenario: Citation invariant
- **WHEN** the baseline pytest runs
- **THEN** every citation emitted by the deterministic QA stub resolves to an existing segment with a non-empty locator, otherwise the test fails
