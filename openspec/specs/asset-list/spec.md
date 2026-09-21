# asset-list Specification

## Purpose
Assets SHALL be listable with offset/limit pagination so workspaces containing more than 1000 assets can be fully inspected without silent truncation.

## Requirements

### Requirement: Paginated asset listing

The system SHALL expose `GET /api/v1/assets` with optional query parameters `offset` (default 0, minimum 0) and `limit` (default 1000, minimum 1, maximum 5000). When `collection_id` is provided, pagination applies within that collection only.

#### Scenario: Default listing (backward compatible)
- **WHEN** `GET /api/v1/assets` is called with no offset or limit
- **THEN** up to 1000 assets are returned, matching the existing behavior

#### Scenario: Paged listing
- **WHEN** `GET /api/v1/assets?offset=1000&limit=100` is called
- **THEN** exactly 100 assets are returned starting from position 1000 (0-indexed)

#### Scenario: Limit cap enforced
- **WHEN** `limit` exceeds 5000
- **THEN** the server returns a 422 validation error

#### Scenario: Pagination with collection filter
- **WHEN** `GET /api/v1/assets?collection_id=abc&offset=50&limit=20` is called
- **THEN** only assets belonging to collection `abc` are considered; the page contains up to 20 assets from that collection

### Requirement: Repository pagination

The `AssetRepository.list_all()` method SHALL accept optional `offset` and `limit` parameters and emit `SELECT * FROM asset LIMIT ? OFFSET ?` with the `deleted_at IS NULL` filter applied post-fetch.

#### Scenario: Offset skips rows
- **WHEN** `list_all(offset=5, limit=3)` is called on a repository with 10 non-deleted assets
- **THEN** exactly 3 assets are returned, corresponding to the 6th–8th non-deleted assets in the database

#### Scenario: Deleted assets excluded
- **WHEN** some assets have `deleted_at IS NOT NULL`
- **THEN** they are excluded from the result regardless of offset/limit values
