## Context

Three bugs cause silent correctness failures in retrieval:
1. `vision_embed.py:89` calls `.shape[-1]` on a string ID → AttributeError → silent default to 128
2. `workspace.py:338` uses `segment_ids` which can be None → potential AttributeError
3. `image_backend.py` zero-vector fallback → returns random tiles as "matches"

The double SearchService is a related design seam creating API confusion.

## Goals / Non-Goals

**Goals:**
- Fix all three correctness bugs with targeted changes
- Delete/unify the SearchService ambiguity
- Add regression tests

**Non-Goals:**
- Refactoring the entire retrieval pipeline
- Adding new search algorithms
- Changing FTS5 or RTree behavior

## Decisions

### D1: Read dimension from actual vector data
**Choice**: Use `index_vectors[0]` or the embedder's configured output_dim instead of `index.ids()[0].shape[-1]`.
**Rationale**: String IDs have no `.shape` attribute; the correct source of truth is the vector data or the model config.

### D2: Guard segment_ids with explicit initialization
**Choice**: Initialize `segment_ids: list[str] = []` before any conditional assignment.
**Rationale**: One-line fix, eliminates the None-append crash path.

### D3: Abstain instead of returning zero-vector matches
**Choice**: When the vision embedder is unavailable, return `[]` from `_image_search()` and log a warning.
**Rationale**: Zero-vector cosine similarity is meaningless — every tile has the same score. Returning empty is honest; returning random tiles is misleading.

### D4: Delete SearchService wrapper
**Choice**: Remove `geomemory/services/search_service.py`.
**Rationale**: It's unused by Workspace.search() and confusing. The retrieval-layer class is the canonical implementation.

## Risks / Trade-offs

- **[Risk] Vision dimension fallback value**: If we can't read the actual dimension, what default? **Mitigation**: Use the embedder's known dimension (e.g., 768 for OLMoEarth Nano) as the documented default, logged as a warning.
- **[Risk] Deleting SearchService wrapper breaks external users**: **Mitigation**: This is alpha v0.1; grep for external usage first.
- **[Risk] Zero-vector abstention changes search results**: **Mitigation**: Current behavior (random tiles) is worse; abstention is the correct fallback.

## Migration Plan

1. Fix `vision_embed.py:89` — read dimension from vector
2. Fix `workspace.py:338` — null-safe segment_ids
3. Fix `image_backend.py` — abstain on zero-vector
4. Delete `services/search_service.py` and verify no broken imports
5. Run full test suite
6. Add regression tests
