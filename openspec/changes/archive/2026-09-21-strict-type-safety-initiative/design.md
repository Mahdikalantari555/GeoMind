## Context

Three layers of type-safety gaps exist:
1. **Boundary gap**: 3 of 4 libs lack `py.typed`, so mypy skips 11 imports in the server
2. **Geomemory gap**: 65 strict-mode errors across 31 files (any-return, arg-type, union-attr, protocol mismatches)
3. **Data_engine gap**: 780 errors, many from incomplete refactors with broken class references

These are independent work streams that share the same goal: zero mypy errors with `--strict`.

## Goals / Non-Goals

**Goals:**
- Add `py.typed` to all 4 libraries
- Fix geomemory's 65 errors systematically
- Fix data_engine's broken references (highest ROI first)
- Enable full strict checking in the server

**Non-Goals:**
- Rewriting poorly-typed code for style points
- Adding type annotations where none are needed (runtime-dynamic code)
- Fixing third-party stub issues (shapely, geopandas, rasterio) — these stay suppressed

## Decisions

### D1: Phase the data_engine cleanup
**Choice**: Fix runtime-breaking errors first (non-existent class references), then tackle stylistic type gaps.
**Rationale**: The broken references cause actual import-time failures. The 780 count includes many minor issues that can be addressed incrementally.

### D2: Suppress third-party missing-stub errors
**Choice**: Keep `import-untyped` suppression for third-party libs (shapely, geopandas, rasterio, fitz, qdrant_client) — these are not under our control.
**Rationale**: Adding stub packages for each would be maintenance burden with little ROI.

### D3: Remove import-untyped suppression only after all py.typed markers are in place
**Choice**: Do NOT remove the server's `disable_error_code = ["import-untyped"]` until all 4 libs have `py.typed` and the 11 errors are confirmed resolved.
**Rationale**: Premature removal would cause CI failures.

## Risks / Trade-offs

- **[Risk] 780 data_engine errors is a large surface** → Mitigation: Tackle in phases; start with the broken references that cause runtime crashes.
- **[Risk] Some geomemory errors require architectural changes** (e.g., protocol mismatches in index backends) → Mitigation: Each error is analyzed individually; some may need interface changes, others just annotation fixes.

## Migration Plan

1. Add `py.typed` to all 4 libs (1 day)
2. Fix server's 11 import-untyped errors (they disappear automatically)
3. Fix geomemory's 65 errors by category:
   - Phase A: no-any-return (~12 errors) — narrow return types
   - Phase B: arg-type Literal vs str (~6 errors) — use Literal types
   - Phase C: union-attr / attr-defined (~5 errors) — add None checks
   - Phase D: protocol mismatches (~8 errors) — align Signatures
   - Phase E: remaining misc (~34 errors)
4. Fix data_engine's broken class references (PipelineSettings→correct name, etc.)
5. Remove `disable_error_code = ["import-untyped"]` from server pyproject.toml
6. Run mypy --strict across all projects
