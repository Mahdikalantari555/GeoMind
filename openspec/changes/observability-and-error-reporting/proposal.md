## Why

Production code across `libs/geomemory` and `libs/geoagent` contains bare `except: pass` and silent `continue` blocks that swallow exceptions during ingest, search, index management, and playbook parsing. These silent failures make it impossible to diagnose why embeddings are missing, why dense-search falls back unexpectedly, or why playbooks fail to load — turning transient issues into persistent data gaps with no log trail.

## What Changes

- Replace every bare `except Exception: pass` (and `except Exception:` without body) in the identified production files with structured `logger.warning(...)` or `logger.info(...)` calls that include the exception type, message, and relevant context.
- Remove or tighten the blanket-catch patterns in workspace.py `_dense_search`, `_candidate_search`, and `index_service.py` so they distinguish expected soft-failures from genuine errors.
- Add a minimal observability baseline: each catch block logs at the appropriate level (`warning` for unexpected-but-recoverable, `info` for expected-best-effort), enabling downstream alerting via structured JSON logs.
- No new dependencies, no API surface changes, no behavior change for callers — only visibility.

## Capabilities

### New Capabilities
- `error-observability`: Structured logging requirements for exception handling across geomemory and geoagent libraries — defines what must be logged, at what level, and under which conditions (best-effort vs. soft-failure vs. unexpected error).

### Modified Capabilities
- *(none)* — No existing spec-level behaviour is changing; the external observable contract remains identical.

## Impact

- **Files modified**: `libs/geomemory/src/geomemory/core/workspace.py`, `libs/geomemory/src/geomemory/services/index_service.py`, `libs/geomemory/src/geomemory/ingest/pipeline.py`, `libs/geoagent/src/geoagent/playbooks.py`
- **No API change**: Gateway endpoints, SSE events, job lifecycle, and client contracts are unaffected.
- **No new dependencies**: Uses Python stdlib `logging` / `structlog` already present in the codebase.
- **No lib boundary violation**: All changes are within `libs/geomemory` and `libs/geoagent`; the server app does not import these internals directly.
- **Test impact**: Existing tests that assert silence on failure paths may need minor updates if they inspect logs.
