## Why

Four libraries lack `py.typed` markers, causing mypy to skip type checking across lib boundaries (11 suppressed `import-untyped` errors in the server). Additionally, geomemory has 65 mypy strict errors across 31 files, and data_engine has 780 errors from incomplete refactors. These gaps mean type safety violations slip through CI undetected.

## What Changes

- Add empty `py.typed` marker files to `libs/geoagent/`, `libs/geolearn/`, `libs/data_engine/`
- Systematically fix geomemory's 65 mypy strict errors (no-any-return, arg-type, union-attr, protocol mismatches)
- Address data_engine's 780 errors — at minimum fix the broken references to non-existent classes (PipelineSettings, process_scene, AnchorPixelManager) that cause runtime crashes
- Add `py.typed` to geomemory as well for completeness
- Run mypy --strict across all libs and verify zero errors

## Capabilities

### New Capabilities
- `strict-type-safety`: All libraries SHALL declare `py.typed` and pass `mypy --strict` with zero errors.

### Modified Capabilities
- *(none)* — no behavioral changes, purely type-system improvements

## Impact

| Area | Detail |
|---|---|
| `libs/geoagent/pyproject.toml` | No change needed (already has mypy config) |
| `libs/geoagent/src/geoagent/py.typed` | NEW: empty file |
| `libs/geolearn/src/geolearn/py.typed` | NEW: empty file |
| `libs/data_engine/src/data_engine/py.typed` | NEW: empty file |
| `libs/geomemory/src/geomemory/py.typed` | NEW: empty file |
| `libs/geomemory/src/geomemory/` | Fix 65 mypy errors |
| `libs/data_engine/src/data_engine/` | Fix 780 mypy errors (prioritize runtime-breaking ones) |
| `server/pyproject.toml` | May remove `disable_error_code = ["import-untyped"]` after py.typed added |
