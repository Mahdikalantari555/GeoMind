# docker-deployment — Spec Delta

## MODIFIED Requirements

### Requirement: Default demo front is Studio

The `docker compose` single-box demo SHALL serve the `apps/studio` production
build as its default front, proxying `/api` to the gateway. The frozen
`apps/web` admin console SHALL remain available only behind an explicit
`reference` profile. The gateway SHALL continue to run as a single uvicorn
worker (SQLite single-writer invariant) and SHALL bind to loopback by default
per `product-hardening-and-trust`.

#### Scenario: default demo shows Studio

- **WHEN** a user runs `docker compose up` with no profile selected
- **THEN** the exposed web port serves the Studio app and its `/api` proxy reaches the gateway

#### Scenario: reference console is opt-in

- **WHEN** the `reference` profile is enabled
- **THEN** the frozen `apps/web` service is also started

### Requirement: Published baseline

The project SHALL publish a repeatable benchmark report at
`docs/benchmarks/report.md` containing a retrieval-parity ablation table,
abstention precision/recall and machine-checked citation correctness, with a
CI regression hook so the numbers cannot silently rot. The README SHALL carry a
summary results table.
