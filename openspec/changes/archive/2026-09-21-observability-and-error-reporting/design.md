## Context

Multiple `except Exception: pass` and silent `continue` patterns exist across geomemory and geoagent. These swallow errors during:
- Vision embedding during raster ingest (workspace.py:360)
- Dense search fallback (workspace.py:806)
- Candidate memory search (workspace.py:858)
- Index service operations (index_service.py:90, 240, 273, 304)
- Batch ingestion (pipeline.py:273)
- Playbook parsing (playbooks.py:92)

Each represents a point where a real error becomes an invisible data gap.

## Goals / Non-Goals

**Goals:**
- Replace every bare `pass` in exception handlers with structured logging
- Scope broad `except Exception:` catches to narrower types where possible
- Define log-level discipline (warning vs info)

**Non-Goals:**
- Changing the operational behavior (still best-effort, still continue on failure)
- Adding new logging infrastructure (use stdlib logging)
- Changing error responses to callers
- Adding structured JSON logging (future change)

## Decisions

### D1: logger.warning for unexpected failures, logger.info for expected best-effort
**Choice**: Vision embed skip = `logger.info` (expected, optional). Search fallback = `logger.warning` (unexpected but recoverable). Playbook parse = `logger.warning` (data quality issue).
**Rationale**: Different levels enable different alerting strategies downstream.

### D2: Include exception type + context in every log message
**Choice**: Every catch block logs `type(exc).__name__` and relevant identifiers (revision_id, path, query prefix).
**Rationale**: Enables search-and-filter in log aggregation tools without dumping full tracebacks.

### D3: Scope broad catches where exception type is known
**Choice**: Replace `except Exception:` with `except (ImportError, RuntimeError, ValueError):` where the failure modes are known, keeping a narrow `except Exception:` with logging as fallback.
**Rationale**: Narrower catches surface programming errors (typos, wrong variable names) that would otherwise be hidden.

## Risks / Trade-offs

- **[Risk] Log volume increase**: More warnings = noisier logs. **Mitigation**: Use `logger.warning` (not `debug`) only for genuinely unexpected events; expected best-effort skips use `logger.info`.
- **[Risk] Test assertions on silence**: Some tests may assert no output on error paths. **Mitigation**: Update tests to expect log records.

## Migration Plan

1. Identify all bare `pass` in except blocks (grep for pattern)
2. Categorize each: expected-best-effort (info) vs unexpected-recoverable (warning)
3. Replace with structured log messages
4. Scope broad catches where possible
5. Update tests that assert silence
6. Run full test suite
