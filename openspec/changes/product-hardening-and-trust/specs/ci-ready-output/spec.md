# ci-ready-output — Spec Delta

## MODIFIED Requirements

### Requirement: Whole-tree verification, not changed-files-only

CI SHALL verify the whole source tree on every push and pull request, not only
files touched by the diff. Library unit tests, the `geomemorytest/` consumer
suite, the gateway tests, the cross-lib integration tests, and both app
builds SHALL run in CI.

#### Scenario: consumer suite runs in CI
- **WHEN** a pull request changes any file
- **THEN** CI runs `pytest libs/geomemory/geomemorytest` in addition to the
  library's own tests

#### Scenario: known failures are explicit
- **WHEN** a consumer-suite test is known to fail for an unrelated reason
- **THEN** it is marked `xfail(strict=True)` so it fails CI the moment it starts
  passing and the waiver can be removed

### Requirement: Lint and type gates fail only on new violations

Full-repo `ruff` and `mypy --strict` SHALL run in CI. Where the tree carries
pre-existing diagnostics, those diagnostics SHALL be recorded in checked-in
baseline files under `scripts/baselines/`. The gate SHALL normalise volatile
path separators and line/column numbers, then fail only when a diagnostic is
present in the current run but absent from the baseline. A diagnostic that
disappears SHALL be reported as informational, not as a failure.

#### Scenario: new lint violation fails the build
- **WHEN** a diagnostic appears that is not in the baseline
- **THEN** the quality-gate job fails and prints the new diagnostic

#### Scenario: pre-existing violations do not fail the build
- **WHEN** the current diagnostics are a subset of the baseline
- **THEN** the quality-gate job succeeds

### Requirement: Dependency audits run in CI

CI SHALL run `pip-audit` for Python dependencies and `pnpm audit
--audit-level=high` for each app. Findings SHALL be reported without blocking
until existing advisories are triaged, after which the steps SHALL become
blocking.

#### Scenario: audit findings are surfaced
- **WHEN** a dependency has a known high-severity advisory
- **THEN** CI emits a warning identifying the affected app or requirements set

### Requirement: One documented Python floor

The declared `requires-python` floor SHALL be exercised by CI. At minimum one
job SHALL build the environment at the floor version (3.10) and verify that all
public packages import and a core test subset passes.

#### Scenario: floor build imports all packages
- **WHEN** CI provisions the Python 3.10 environment
- **THEN** importing `geomemory`, `geoagent`, `geolearn`, `geodomain`,
  `geospatial_core`, `data_engine` and `geofront_api` succeeds

### Requirement: Shared conda environment cache

CI jobs that create the `geospatial` conda environment SHALL share a cache of
conda package archives keyed by `environment.yml`, so repeated jobs reuse
downloaded packages.

#### Scenario: cache hit
- **WHEN** two jobs run with the same `environment.yml` digest
- **THEN** the second job restores the conda package cache from the first
