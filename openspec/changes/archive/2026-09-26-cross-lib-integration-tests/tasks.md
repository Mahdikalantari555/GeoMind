# Tasks

## 1. Shared fixtures and workspace bootstrap

- [x] 1.1 Extract workspace-creation helper from `server/tests/conftest.py` into a
      reusable module `tests/integration/_workspace.py` and verify both suites
      can import it via `conda run -n geospatial pytest server/tests/test_workspace.py tests/integration/ -q`
- [x] 1.2 Add `tests/integration/conftest.py` that creates a temp workspace root,
      sets `embedding_provider="hashing"` (no ONNX download), and provides a
      `gateway` fixture returning a `starlette.TestClient` over the real FastAPI app
- [x] 1.3 Add a `_llm_backend` fixture that monkeypatches
      `geomemory.qa.backend_factory.build_llm_backend` to return a deterministic
      stub, and verify `POST /api/v1/ask` returns `200` with a non-empty `citations` list

## 2. Gateway↔geomemory ingest roundtrip

- [x] 2.1 Implement `tests/integration/test_gateway_core_roundtrip.py::test_ingest_text_document`
      and verify `GET /api/v1/assets` returns the record with a SHA-256 matching
      the uploaded content
- [x] 2.2 Implement `test_ingest_geojson_vector` using `sample/sasmple.geojson` content
      and verify the record `kind` is `vector` and status is `201`

## 3. Real dense search through the gateway

- [x] 3.1 Implement `test_search_returns_real_dense_hits`: ingest a document containing
      "NDVI", call `POST /api/v1/search` with `mode="dense"`, and verify at least one
      hit with a non-null `dense_score` and a `locator` referencing a persisted segment id

## 4. Citation provenance chain integrity

- [x] 4.1 Implement `test_ask_citations_resolve`: ingest a document, call
      `POST /api/v1/ask`, and verify each citation `segment_id` resolves to a row in
      the `segment` table, each `asset_revision_id` resolves to `asset_revision`,
      and the revision `hash` resolves to a file under `objects/sha256/`

## 5. Agent tool execution against a real workspace

- [x] 5.1 Implement `test_agent_tool_runs_on_workspace`: ingest a document, call
      `POST /api/v1/agent/run` with a valid read-only tool name and args, and verify
      the response status is `200`, `status` is `"ok"`, and `artifacts` reference
      workspace paths

## 6. SQLite single-writer serialization

- [x] 6.1 Implement `test_concurrent_writes_serialize`: fire 8 concurrent
      `POST /api/v1/asset` requests against the same workspace and verify all
      succeed with distinct ids, the `asset` table contains exactly 8 rows, and no
      request returns a `500` with a `database is locked` error

## 7. data-engine↔agent bridge with synthetic data

- [x] 7.1 Add `tests/integration/_raster_fixture.py` generating a 4-band synthetic
      GeoTIFF over the bounds of `sample/sasmple.geojson` and verify it writes a
      valid file readable by `rasterio`
- [x] 7.2 Implement `test_agent_geo_zonal_stats_on_synthetic_raster`: invoke the
      `geo_zonal_stats` tool with the synthetic raster and `sample/sasmple.geojson`
      as AOI, and verify the result contains zonal statistics whose bounds fall
      inside the raster extent, with no network calls to Planetary Computer or
      Open-Meteo

## 8. Full suite gate

- [x] 8.1 Run `conda run -n geospatial pytest tests/integration -q` and verify all
      tests pass with zero failures
- [x] 8.2 Run `conda run -n geospatial ruff check tests/integration` and verify zero
      lint violations
- [x] 8.3 Run `conda run -n geospatial mypy --strict tests/integration` and verify
      zero type errors