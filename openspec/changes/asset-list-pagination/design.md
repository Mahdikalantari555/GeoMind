## Context

The asset listing pipeline has three tiers of silent data loss and performance debt:
- `BaseRepository.list_all()` silently truncates at 1000 rows with no `total` or indication of truncation
- `Workspace.stats()` issues a separate `COUNT(*)` query per revision_id, causing N+1 serial SELECTs that scale linearly with asset count
- `files.py` accesses the private `service._settings.workspace` attribute instead of going through the public facade

These are independently fixable but share the same root cause: the facade layer lacks methods that the server needs directly.

## Goals / Non-Goals

**Goals:**
- Add `offset`/`limit` parameters to `list_all()` and `list_assets()` so large workspaces can page through results
- Replace the per-revision COUNT loop in `stats()` with aggregated GROUP BY queries
- Add `get_workspace_path()` to the Workspace facade so `files.py` no longer reaches into private attributes
- Preserve backward compatibility: default `limit=1000, offset=0` keeps current behavior unchanged

**Non-Goals:**
- Full cursor-based pagination (offset is sufficient for current use case)
- Adding total-count headers to the response (future enhancement)
- Changing the ingestion or search pipelines

## Decisions

### D1: Default limit=1000 preserved
**Choice**: `BaseRepository.list_all(limit=1000, offset=0)` — callers that do not pass params get identical results.
**Rationale**: Existing tests, server routers, and the web UI all rely on the current behavior. A breaking change here would require updating every caller simultaneously, increasing risk with no user-facing benefit.

### D2: Stats uses GROUP BY instead of per-revision COUNT
**Choice**: Three queries with `GROUP BY revision_id` replacing the N×3 loop.
**Rationale**: One query per table per workspace instead of one per revision. For 100 assets this drops from ~300 queries to 3. SQLite handles GROUP BY efficiently with the existing index on `revision_id`.

### D3: `get_workspace_path()` added to Workspace facade
**Choice**: `Workspace.get_workspace_path() -> Path` returns the resolved workspace directory path.
**Rationale**: `files.py` currently accesses `service._settings.workspace` (private). Adding this to the facade aligns with the public-service-boundary change and eliminates the `# type: ignore[union-attr]` pattern.
