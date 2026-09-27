## ADDED Requirements

### Requirement: Dynamic default workspace root
The gateway SHALL dynamically resolve the default workspace root to `<project_root>/Workspaces` in development environments and `/workspace` in container environments, overridable by `GEOFOND_WORKSPACE`. It SHALL NOT depend on hardcoded machine-specific paths.

#### Scenario: Workspace creation with empty path
- **WHEN** `POST /api/v1/workspace/create` is requested with an empty or omitted path
- **THEN** the workspace directory is created under the dynamically resolved project root `Workspaces/` directory without permission errors or hardcoded path failures

### Requirement: Robust ingestion request validation
The gateway SHALL accept multipart file uploads for `POST /api/v1/ingest` and JSON payloads for `POST /api/v1/ingest/bytes`, returning clear 422 error structures with specific field names when required attributes (`file`, `collection_id`) are missing.

#### Scenario: Missing collection id
- **WHEN** a client submits a file upload to `POST /api/v1/ingest` without `collection_id`
- **THEN** the gateway returns `422 Unprocessable Entity` with a descriptive validation error identifying `collection_id`
