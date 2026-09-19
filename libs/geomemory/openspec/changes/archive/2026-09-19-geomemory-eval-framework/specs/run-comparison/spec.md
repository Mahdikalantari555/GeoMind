## Purpose

Compares two persisted benchmark runs and surfaces regressions: statistics
drift, per-query retrieval differences, missing results, and newly discovered
results. Designed for rapid developer regression detection.

## ADDED Requirements

### Requirement: Comparison input
Comparison SHALL accept two existing run directories under `geomemory-evals/runs/`.

#### Scenario: Valid inputs
- **WHEN** two run directories are supplied
- **THEN** comparison proceeds

#### Scenario: Missing input
- **WHEN** a supplied run directory does not exist
- **THEN** comparison fails with a clear error naming the missing path

### Requirement: Statistics diff
Comparison SHALL diff the `stats.json` of both runs and report the delta for
every numeric field.

#### Scenario: Chunk count drift
- **WHEN** run A has `chunks: 418` and run B has `chunks: 430`
- **THEN** the report shows `chunks: 418 -> 430 (+12)`

#### Scenario: No drift
- **WHEN** both runs have identical stats
- **THEN** the report shows no statistics changes

### Requirement: Retrieval diff
Comparison SHALL compare per-query rows between runs with matching query text
and report, per query: retrieved-id set differences, missing results (in A not
B), and newly discovered results (in B not A).

#### Scenario: Missing result
- **WHEN** query Q returns `[a, b]` in run A and `[a]` in run B
- **THEN** the report flags `b` as missing in run B

#### Scenario: New result
- **WHEN** query Q returns `[a]` in run A and `[a, c]` in run B
- **THEN** the report flags `c` as newly discovered in run B

#### Scenario: Query present in one run only
- **WHEN** a query exists in run A but not run B
- **THEN** the report flags the query as absent in run B

### Requirement: Comparison output
Comparison SHALL emit a machine-readable diff (JSON) and a human-readable
summary highlighting changed statistics and retrieval differences.

#### Scenario: Output format
- **WHEN** comparison completes
- **THEN** both a JSON diff and a text summary are produced

### Requirement: Exit code
Comparison SHALL exit non-zero when any statistically or retrieval-relevant
difference is detected, and zero when runs are equivalent.

#### Scenario: Difference detected
- **WHEN** runs differ
- **THEN** the process exits with a non-zero code

#### Scenario: Runs equivalent
- **WHEN** runs are identical
- **THEN** the process exits with code 0