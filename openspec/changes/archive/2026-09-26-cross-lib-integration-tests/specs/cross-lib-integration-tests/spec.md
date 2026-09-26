# cross-lib-integration-tests

Repo-root integration tests that exercise the gateway↔`geomemory`↔`geoagent`
seams with real facades and synthetic data.

## Requirements

### Requirement 1: Gateway↔geomemory ingest roundtrip

The gateway must persist assets through the real `GeoMemory` facade and return
them via the HTTP API without mocking library internals.

**Scenario: ingest document and list assets**

- Given a temporary workspace root with an empty object store
- When `POST /api/v1/asset` is called with a text document
- Then the response contains an `id` and a `sha256` matching the content hash
- And `GET /api/v1/assets` returns the record with identical `sha256`

**Scenario: ingest GeoJSON vector**

- Given a temporary workspace root
- When `POST /api/v1/asset` is called with `sample/sasmple.geojson` content
- Then the response status is `201`
- And the record `kind` is `vector`

### Requirement 2: Real dense search through the gateway

`POST /api/v1/search` must return hits produced by `geomemory.retrieval.search_service.SearchService`,
not by mocked backends.

**Scenario: search returns real dense hits**

- Given a workspace with one ingested document containing the text "NDVI"
- When `POST /api/v1/search` is called with `query="NDVI"` and `mode="dense"`
- Then the response contains at least one hit
- And each hit has a non-null `dense_score`
- And each hit `locator` references a persisted segment id

### Requirement 3: Citation provenance chain integrity

`POST /api/v1/ask` must produce an answer whose provenance chain
(`answer → citation → segment → asset_revision → objects/<sha256>`) is intact.

**Scenario: ask returns verifiable citations**

- Given a workspace with an ingested document
- When `POST /api/v1/ask` is called with a question answerable from the document
- Then the response contains an `answer` and a non-empty `citations` list
- And each citation `segment_id` resolves to a row in the `segment` table
- And each cited segment's `asset_revision_id` resolves to a row in `asset_revision`
- And the asset revision's `hash` resolves to a file under `objects/sha256/`

### Requirement 4: Agent tool execution against a real workspace

`POST /api/v1/agent/run` must invoke a `geoagent` tool/playbook against the
ingested workspace and return a structured result.

**Scenario: run a read-only agent tool**

- Given a workspace with an ingested document
- When `POST /api/v1/agent/run` is called with a valid tool name and args
- Then the response status is `200`
- And the response contains a `status` of `"ok"`
- And the response contains `artifacts` referencing workspace paths

### Requirement 5: SQLite single-writer serialization

Concurrent gateway requests against the same workspace must serialize writes
behind `AppState.write_lock` with no `database is locked` / `SQLITE_BUSY`
errors.

**Scenario: concurrent writes do not collide**

- Given a workspace with an empty object store
- When N concurrent `POST /api/v1/asset` requests are issued
- Then all N requests succeed with distinct `id`s
- And the SQLite `asset` table contains exactly N rows
- And no request returns a `500` with a `database is locked` error

### Requirement 6: data-engine↔agent bridge with synthetic data

The `geoagent` GIS tooling must consume data-engine outputs (raster metadata,
zonal stats) when given synthetic rasters and `sample/sasmple.geojson` as ROI,
without performing any real satellite fetch.

**Scenario: agent GIS tool runs on synthetic raster + sample AOI**

- Given a synthetic GeoTIFF fixture and `sample/sasmple.geojson` as ROI
- When a `geoagent` GIS tool is invoked with the raster path and AOI
- Then the tool returns zonal statistics over the AOI
- And the result bounds fall inside the raster extent
- And no network call to Planetary Computer or Open-Meteo is made