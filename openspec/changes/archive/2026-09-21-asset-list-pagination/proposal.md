## Why

`GET /api/v1/assets` returns all assets in a collection but silently truncates at 1000 rows with no indication to the caller. Workspaces with more than 1000 assets show incomplete lists in the web UI, and there is no way for a client to page through results. This is a correctness gap that will surface as missing data in production workspaces.

## What Changes

- Add `offset` and `limit` query parameters to `AssetRepository.list_all()` (default `limit=1000`, `offset=0` for backward compatibility)
- Add `offset` and `limit` parameters to `Workspace.list_assets(collection_id, *, offset=0, limit=1000)`
- Add `offset` and `limit` query parameters to `GET /api/v1/assets` endpoint in the gateway
- Regenerate the web API client so TypeScript types include the new params
- The default `limit=1000` preserves current behavior — only callers that explicitly pass params get pagination

## Capabilities

### New Capabilities
- `asset-pagination`: Defines the paginated listing behavior for the assets endpoint — required `collection_id` filter, optional `offset`/`limit` with defaults, response shape including total count.

### Modified Capabilities
- *(none)* — No existing spec-level requirement is changing; this adds a new capability.

## Impact

- **libs/geomemory** (`src/geomemory/storage/repositories/base.py`, `src/geomemory/core/workspace.py`): Adds pagination params to `list_all()` and `list_assets()`
- **server** (`src/geofront_api/routers/ingest.py`): Adds `offset`/`limit` query params to `GET /api/v1/assets`
- **apps/web**: Regenerated API client includes new params
- **Backward compatible**: Default `limit=1000, offset=0` preserves existing behavior for all current callers
- **No schema change**: SQL `LIMIT`/`OFFSET` uses existing columns, no DDL migration
