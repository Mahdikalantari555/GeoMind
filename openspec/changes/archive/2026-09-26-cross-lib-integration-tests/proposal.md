# Proposal

## Why

Unit tests verify each library in isolation; nothing exercises the seams where
`geomemory`, `geoagent`, and the `geofront_api` gateway actually meet. The
`full-stack-audit-and-bug-fixes` change will touch router contracts and the web
client, but there is no automated gate that proves the gateway still ingests,
indexes, searches, and answers through real facades rather than mocks. This
change adds that gate as a separate, low-risk change so the audit change stays
focused on frontend/server surfaces.

## What Changes

1. Add a repo-root `tests/integration/` directory with a shared conftest that
   spins up a temporary workspace root and runs the gateway (uvicorn) in a
   threadpool against it.
2. Add integration tests covering the gateway→core roundtrip:
   - POST `/api/v1/asset` ingest (document + GeoJSON vector) → GET
     `/api/v1/assets` returns persisted records with SHA-256 identity.
   - POST `/api/v1/search` returns real dense hits backed by `geomemory`
     `SearchService`, not mocks.
   - POST `/api/v1/ask` returns a citation-grounded answer whose provenance
     chain (`answer → citation → segment → asset_revision → objects/<sha256>`)
     is intact and verifiable.
   - POST `/api/v1/agent/run` invokes a `geoagent` playbook/tool against the
     ingested workspace and returns a structured result.
3. Add a synthetic data-engine fixture test: feed `sample/sasmple.geojson` as
   ROI into `geoagent` GIS tools (zonal stats, raster metadata) with mocked
   raster inputs, proving the agent SDK can consume data-engine outputs
   without real satellite fetch.
4. Add a SQLite single-writer concurrency test: fire N concurrent gateway
   requests at the same workspace and assert no `database is locked` /
   `SQLITE_BUSY` errors and writes serialize behind `AppState.write_lock`.

## Capabilities

### New Capabilities
- `cross-lib-integration-tests`: Repo-root integration suite exercising the
  gateway↔`geomemory`↔`geoagent` seams with real facades and synthetic data,
  plus a SQLite write-lock serialization gate.

### Modified Capabilities
*(none — no spec-level behavior changes; tests only.)*

## Impact

- **New files**: `tests/integration/conftest.py`, `tests/integration/test_gateway_core_roundtrip.py`,
  `tests/integration/test_agent_tool_on_workspace.py`, `tests/integration/test_concurrent_writes.py`,
  `tests/integration/test_data_engine_agent_bridge.py`
- **Modified files**: `server/tests/conftest.py` (extract shared workspace fixture
  so integration tests reuse it), `pyproject.toml` at repo root if a pytest
  `testpaths` entry is added.
- **Deps**: no new runtime deps. Uses existing `httpx`/`anyio` test clients
  already present in `server/tests`.
- **Tests**: all new; run via `conda run -n geospatial pytest tests/integration -q`.