# Plan 008: Fix ingest dedup to respect the requested collection and soft-deleted assets

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- libs/geomemory/src/geomemory/core/workspace_ingest.py libs/geomemory/src/geomemory/core/workspace_internals.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/007-geomemory-write-rollback.md recommended first
  (same file), but technically independent
- **Category**: bug
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

The ingest dedup path matches content by SHA-256 hash and returns the
**existing** asset regardless of (a) which collection the caller asked for
and (b) whether that asset was soft-deleted. Two failures follow:

1. Uploading the same file to collection B returns an asset that lives in
   collection A — and the gateway then publishes `asset_created` with
   `collection_id` B, so the UI and citation chain point at the wrong
   collection.
2. After an asset is soft-deleted, re-ingesting the same content raises
   `AssetNotFoundError` **forever** — the hash row is never cleaned, and the
   dedup path looks the asset up through a helper that rejects soft-deleted
   rows.

## Current state

- `libs/geomemory/src/geomemory/core/workspace_ingest.py:71-88`:
  ```python
  # Dedup check: reuse existing revision with same hash.
  existing = self.conn.execute(
      "SELECT * FROM asset_revision WHERE hash = ? LIMIT 1", (content_hash,)
  ).fetchone()
  if existing is not None:
      asset = self._asset_by_id(existing["asset_id"])
      existing_segments = self._segments_for_revision(existing["id"])
      if existing_segments is not None:
          segment_ids = [s.id for s in existing_segments]
      return _job_completed(
          "ingestion",
          {
              "asset_id": asset.id,
              "revision_id": existing["id"],
              "skipped": True,
              "reason": "duplicate hash",
          },
      )
  ```
- `libs/geomemory/src/geomemory/core/workspace_internals.py:32-38` — the
  helper rejects soft-deleted assets:
  ```python
  def _asset_by_id(self, asset_id: str) -> Asset:
      from geomemory.storage.repositories.asset_repo import AssetRepository
      asset = AssetRepository(self.conn).get(asset_id)
      if asset is None or asset.deleted_at is not None:
          raise AssetNotFoundError(f"Asset not found: {asset_id}")
      return asset
  ```
- The asset row's `collection_id` column is available on the fetched `asset`.
- Downstream: `routers/ingest.py:93-100` publishes `asset_created` with the
  requested `collection_id` on skipped ingests too — after this fix the
  skipped case only happens when the asset genuinely lives in the requested
  collection, so the event becomes truthful. (No gateway change needed.)
- `self.objects.put_bytes(raw)` later in the normal path is content-addressed
  and idempotent — re-storing identical bytes is safe (it returns the same
  hash; see the `assert stored_hash == content_hash` at ingest.py:102).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| geomemory tests (baseline FIRST) | `cd libs/geomemory && conda run -n geo pytest tests -q` | record failure set (known Windows pre-existing: CLI dashboard, lance backend, olmoearth multichannel) |
| geomemory tests (after) | same | identical failure set |
| Integration | `conda run -n geo pytest tests -q` | 8 passed |
| Lint | `conda run -n geo ruff check libs/geomemory/src` | exit 0 |

## Scope

**In scope**:
- `libs/geomemory/src/geomemory/core/workspace_ingest.py` (dedup block only)
- New/extended unit test under `libs/geomemory/tests/unit/`

**Out of scope**:
- Hash-row cleanup for deleted assets (schema/GC concern) — separate change.
- The gateway's `asset_created` event logic.
- `workspace_internals.py` `_asset_by_id` semantics (other callers depend on
  the soft-delete rejection).

## Git workflow

- Branch: `advisor/008-ingest-dedup-fix`
- Commit: `fix(geomemory): ingest dedup honors target collection and deleted assets`

## Steps

### Step 1: Record the baseline

Run the geomemory suite; note failures for comparison.

### Step 2: Rewrite the dedup block

Replace `workspace_ingest.py:71-88` with logic that decides between
"skip" and "fall through":

```python
# Dedup check: reuse existing revision with same hash — but only when the
# existing asset is alive AND already in the requested collection.
existing = self.conn.execute(
    "SELECT * FROM asset_revision WHERE hash = ? LIMIT 1", (content_hash,)
).fetchone()
reuse = False
if existing is not None:
    from geomemory.storage.repositories.asset_repo import AssetRepository

    existing_asset = AssetRepository(self.conn).get(existing["asset_id"])
    if (
        existing_asset is not None
        and existing_asset.deleted_at is None
        and existing_asset.collection_id == collection_id
    ):
        reuse = True
        existing_segments = self._segments_for_revision(existing["id"])
        if existing_segments is not None:
            segment_ids = [s.id for s in existing_segments]
        return _job_completed(
            "ingestion",
            {
                "asset_id": existing_asset.id,
                "revision_id": existing["id"],
                "skipped": True,
                "reason": "duplicate hash",
            },
        )
# else: fall through to the normal ingest path. For a cross-collection
# duplicate this creates a new asset in the requested collection sharing
# the stored object (objects.put_bytes is idempotent by hash). For a
# soft-deleted duplicate it effectively re-ingests under a new asset id.
```

Notes:
- The local import style matches the file (`workspace_internals.py` imports
  repositories inside methods — follow the file's existing import pattern;
  a module-level import of `AssetRepository` is fine if ruff/mypy are happy,
  but match what the file already does).
- The plain `AssetRepository.get` (not `_asset_by_id`) deliberately does NOT
  raise on soft-deleted rows.
- The `reuse` flag is only needed if subsequent code branches on it; if the
  `return` covers the whole skip case, drop the flag — keep the diff minimal
  and readable.

**Verify**: `cd libs/geomemory && conda run -n geo pytest tests -q` → identical failure set to baseline.

### Step 3: Regression tests

Add unit tests (next to existing ingest unit tests):

1. **Cross-collection duplicate**: ingest `file.txt` into collection A →
   success. Ingest the same content into collection B → assert the result
   is NOT `skipped`, a NEW asset id is returned, and
   `ws.get_asset(new_id).collection_id == B.id`; assert the object store
   did not duplicate bytes (the sha256 path under `objects/` exists once —
   via `ws.objects.get_path(hash)` or the store's public API).
2. **Deleted-asset re-ingest**: ingest → soft-delete the asset
   (`ws.delete_asset(...)` — check the exact facade method name in
   `workspace_assets.py`; if deletion is via a different entry point, use
   that). Re-ingest the same content → assert success with a NEW asset id
   (no `AssetNotFoundError`).
3. **Same-collection duplicate**: re-ingest into the same collection →
   still returns `skipped: True` with the same asset id (existing behavior
   preserved; likely already covered — extend rather than duplicate).

**Verify**: `conda run -n geo pytest <tests> -q` → pass; full suite failure set unchanged.

## Test plan

- Three unit tests above (cross-collection, deleted-asset, same-collection).
- Repo-root integration suite must stay 8/8 (it exercises ingest+search).
- Lint/typecheck: no new errors vs baseline.

## Done criteria

- [ ] geomemory suite: identical failure set to baseline
- [ ] `conda run -n geo pytest tests -q` → 8 passed
- [ ] New dedup tests pass
- [ ] `conda run -n geo ruff check libs/geomemory/src` → exit 0
- [ ] No gateway or app files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- `AssetRepository.get` semantics differ from the excerpt (raises, or
  returns deleted rows filtered) — report what it actually does.
- The facade's soft-delete entry point doesn't exist under a greppable name
  (`delete_asset` / `archive_asset` / `soft_delete`) — report the actual
  API rather than improvising.
- Existing tests assert the old cross-collection skip behavior — report;
  that expectation change is intended but must be flagged to the owner.

## Maintenance notes

- The `asset_created` SSE event now always carries a truthful
  `collection_id` for skipped ingests — no gateway edit needed, but note it
  in the commit body.
- If the owner later wants "same bytes, multiple collections" deduplicated
  at the object level with collection-scoped revision rows, that is a schema
  evolution — openspec change.
- Reviewer should scrutinize: no behavior change for the same-collection
  duplicate path; soft-deleted lookup does not raise.
