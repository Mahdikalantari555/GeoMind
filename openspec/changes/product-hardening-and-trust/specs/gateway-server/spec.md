# gateway-server — Spec Delta

## MODIFIED Requirements

### Requirement: Authentication and authorization

The gateway SHALL reject `/api/v1` requests lacking a valid bearer token when
`GEOMIND_AUTH` is enabled (401 `unauthorized`). Settings, provider, environment
and model-download routes SHALL require an admin-scoped token (403 `forbidden`).
The server SHALL bind `127.0.0.1` unless `GEOMIND_BIND=0.0.0.0`; CORS origins
SHALL come from `GEOMIND_CORS_ORIGINS` (default: dev list).

#### Scenario: unauthenticated mutation is rejected
- **WHEN** `POST /api/v1/workspace/settings` has no token
- **THEN** 401 is returned and no state changes

### Requirement: Secret handling

No response SHALL contain `llm_api_key`, `qdrant_api_key` or
`cloudflare_api_token`. These SHALL be written only to process env, never to
the workspace DB or `settings.yaml`; responses expose only configured flags.
Validation error details SHALL NOT include submitted `input` values.

#### Scenario: key is accepted but not echoed
- **WHEN** a client sets `qdrant_api_key` and reads settings
- **THEN** `qdrant_key_configured: true` is returned with no key value

### Requirement: Error and event disclosure

Job errors SHALL be stable codes + correlation ids, never raw exception strings.
`/events` SHALL publish only id/status/stage/progress, never job `result`;
clients refetch results from the authenticated jobs endpoint.

### Requirement: Input contracts and sandbox containment

Feedback routes SHALL use typed Pydantic bodies (`extra="forbid"`); `roi` SHALL
be a typed GeoJSON Polygon; `agent/files.py` SHALL resolve both sides before the
containment check; farm roots SHALL match the hardened `maps.py` roots and
`farm_id` SHALL be a safe slug.

### Requirement: Job lifecycle

Progress updates SHALL be marshalled onto the event loop; the registry SHALL be
bounded across all statuses (429 `too_many_jobs` when full); shutdown SHALL
propagate cooperative cancellation to long calls; partial downloads SHALL set
`partial: true` with an explicit error list; tiles SHALL be LRU-cached by path,
coordinates, bands and source mtime/size.
