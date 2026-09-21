## 1. Asset pagination — repository layer

- [x] 1.1 In `libs/geomemory/src/geomemory/storage/repositories/base.py`, update `list_all(self, limit: int = 1000, offset: int = 0)` to emit `SELECT * FROM {table} LIMIT ? OFFSET ?` with both params; verify via direct DB call that offset skips the first N rows correctly
- [x] 1.2 In `libs/geomemory/src/geomemory/storage/repositories/asset_repo.py`, add `list_all(limit=1000, offset=0)` override that passes through to `BaseRepository.list_all()` and applies the `deleted_at is None` filter after fetching (to preserve existing filter semantics)

## 2. Asset pagination — Workspace facade

- [x] 2.1 In `libs/geomemory/src/geomemory/core/workspace.py`, update `list_assets(self, collection_id: str | None = None, *, offset: int = 0, limit: int = 1000) -> list[Asset]` to pass `offset` and `limit` to `repo.list_all()` when `collection_id is None`; when `collection_id` is set, keep the existing `get_by_collection()` path unchanged
- [x] 2.2 Verify: a unit test creates >1000 assets (or mocks the repo), calls `list_assets(offset=1000, limit=100)`, and asserts the returned list has length 100 and contains only assets from positions 1000–1099

## 3. Asset pagination — gateway endpoint

- [x] 3.1 In `server/src/geofront_api/routers/ingest.py`, add `offset: int = Query(default=0, ge=0)` and `limit: int = Query(default=1000, ge=1, le=5000)` to `list_assets()`; pass them to `ws.list_assets(collection_id, offset=offset, limit=limit)`
- [x] 3.2 Add OpenAPI validation: `limit` capped at 5000 to prevent runaway queries; document the params in the endpoint docstring
- [x] 3.3 Regenerate the web client (`cd apps/web && pnpm gen:api`) and verify TypeScript types include `offset` and `limit` on the assets GET operation

## 4. Verification

- [x] 4.1 Run `conda run -n geospatial pytest libs/geomemory/tests -q --tb=short` — expect all tests pass
- [x] 4.2 Run `conda run -n geospatial pytest server/tests -q --tb=short` — expect all server tests pass
- [x] 4.3 Run `conda run -n geospatial ruff check libs/geomemory/src server/src` — clean
- [x] 4.4 Run `cd apps/web && pnpm build` — SPA compiles without errors
- [x] 4.5 Update `tasks/todo.md` checkboxes to reflect completion status
