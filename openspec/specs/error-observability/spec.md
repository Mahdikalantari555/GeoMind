# error-observability Specification

## Purpose
Define structured logging requirements for exception handling across geomemory and geoagent libraries, ensuring no silent `pass` in exception handlers obscures root causes.

## Requirements

### Requirement: No bare pass in exception handlers
Every `except` block in production code under `libs/geomemory/src/` and `libs/geoagent/src/` SHALL log at minimum a `logger.warning()` or `logger.info()` message containing the exception type and a brief context description. Bare `pass` is PROHIBITED in non-test production code.

#### Scenario: Vision embed failure during raster ingest
- **WHEN** vision embedding fails during raster asset ingestion
- **THEN** `logger.warning("vision embed skipped for revision %s: %s", revision_id, exc)` SHALL be emitted
- **AND** the ingestion SHALL continue (best-effort semantics preserved)

#### Scenario: Dense search fallback exception
- **WHEN** the persisted index search fails and falls back to n-gram backend
- **THEN** `logger.info("dense index search failed, falling back to n-gram: %s", type(exc).__name__)` SHALL be emitted
- **AND** the n-gram fallback SHALL execute normally

#### Scenario: Candidate memory search exception
- **WHEN** candidate memory search raises an exception
- **THEN** `logger.warning("candidate memory search failed: %s", exc)` SHALL be emitted
- **AND** an empty candidate list SHALL be returned (no crash)

#### Scenario: Playbook parse failure
- **WHEN** a playbook file fails to parse
- **THEN** `logger.warning("skipped invalid playbook %s: %s", path, exc)` SHALL be emitted
- **AND** parsing SHALL continue with remaining playbooks

### Requirement: Log level discipline

Exception handlers SHALL use `logger.warning()` for unexpected-but-recoverable failures (embedding errors, search fallbacks, parse errors), `logger.info()` for expected best-effort skips, and `logger.debug()` only for verbose diagnostic traces outside catch blocks.

#### Scenario: Warning for recoverable failures
- **WHEN** an embedding or search operation fails unexpectedly but is handled gracefully
- **THEN** the handler logs at `warning` level, not `info` or `debug`

#### Scenario: Info for expected skips
- **WHEN** a best-effort optional operation (e.g., vision embed during raster ingest) fails as expected
- **THEN** the handler logs at `info` level

### Requirement: Exception context in log messages
Every log message from an exception handler SHALL include: (a) the operation being performed, (b) the exception type name, and (c) relevant contextual identifiers (revision_id, path, query, etc.)

#### Scenario: Complete log context
- **WHEN** an exception is caught during ingestion
- **THEN** the log message SHALL contain the revision ID or segment identifier
- **AND** the exception type SHALL be included (not just the message string)

### Requirement: blanket exception catches SHALL be scoped
Broad `except Exception:` blocks in search and index paths SHALL be replaced with narrower catches where the exception type is known (e.g., `except (ImportError, RuntimeError):`), with a fallback `except Exception:` that logs at warning level.

#### Scenario: Narrower catches in workspace.py
- **WHEN** `_dense_search()` and `_candidate_search()` handle exceptions
- **THEN** known exception types SHALL be caught explicitly
- **AND** unknown exceptions SHALL fall through to a logged `except Exception:`
