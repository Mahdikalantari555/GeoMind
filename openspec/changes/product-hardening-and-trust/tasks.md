# Tasks — product-hardening-and-trust

Verification gates (run after each section):
- `conda run -n geo pytest server/tests -q && conda run -n geo ruff check server`
- `cd server && conda run -n geo mypy --strict src/`
- `cd libs/geomemory && conda run -n geo pytest -q && conda run -n geo mypy --strict src/`
- `cd libs/geoagent && conda run -n geo pytest -q`
- `cd libs/geolearn && conda run -n geo pytest -q`
- Root: `conda run -n geo ruff check libs/*/src server/src`

## 1. Gateway auth and secret handling (S-006…S-013, G-024)

- [x] 1.1 Bearer-token dependency + admin scope in `auth.py`, applied at router
      registration; `GEOMIND_AUTH=off` dev opt-out. (S-006)
- [x] 1.2 Bind `127.0.0.1` by default; `GEOMIND_BIND` opt-out; env-driven CORS.
      Update Dockerfile/compose/launchers/.env.example. (S-006, S-013, X-086)
- [x] 1.3 Env-route `qdrant_api_key`/`cloudflare_api_token`, configured flags in
      responses, `exclude=True` on lib fields, round-trip test. Rotate keys. (S-007, G-024)
      - Operator follow-up (out of code scope): rotate any credential previously
        written to a workspace or echoed in logs.
- [x] 1.4 Sanitize `errors.py` 422 details; redact job errors and SSE results;
      strip `/health` fields. (S-009, S-010, S-011)
- [x] 1.5 Regression tests: no endpoint reachable unauthenticated, admin routes
      reject non-admin tokens, no credential-named field in any response, and
      422 details never contain submitted secret-like values. (T-079)

## 2. Gateway inputs, sandbox and jobs (S-014, S-015, G-025…G-033)

- [x] 2.1 Typed feedback bodies + GeoJSON `roi` model; `agent/files.py` root
      resolution; `farms.py` roots and `farm_id` slug. (G-026, G-027, S-014, S-015)
- [x] 2.2 Threadpool `AgentService.init()`; loop-safe progress; bounded job
      registry; cooperative shutdown token; partial-download flag; tile cache. (G-028…G-033, G-025)

## 3. Agent runtime and learning (S-018…S-023, L-060…L-069, P-070)

- [x] 3.1 Write-path sandbox: reject absolute `output_*`/`out_*`, validate CLI
      path params, pin plugin hashes, delimit untrusted tool text, validate
      classifier keys, intersect `context_scope`. (S-018…S-023)
- [x] 3.2 Shared budget counter for nested calls; real `meteo_data` dict. (L-061, L-062)
- [x] 3.3 Skip malformed candidates; one entropy function/scale; edge/server
      probability parity; no caller-model mutation; explicit version paths;
      `timezone.utc`; wire or delete `auto_train_on_feedback`, reset drift. (L-063…L-066, L-069, F-099, CORR-10/11, TECH-01)
- [x] 3.4 CRS-aware `polygonize_array`; `geo_reclassify` delegates to core; one
      versioned taxonomy with a cross-lib contract test; cache k-NN embeddings. (L-067, L-068, L-069, P-070)
- [x] 3.5 Negative tests for every sandbox case (absolute output, CLI path,
      collections override, key traversal). (geoagent TEST-01)
- [x] 3.6 Correct the geoagent README "spec phase (no code yet)" status line and
      link the capability inventory. (geoagent DOC-01)

## 4. Geomemory integrity (M-050…M-059, P-071…P-075)

- [x] 4.1 Atomic migrations; soft-delete filters in FTS/dense/image; rollback
      before retry; honour `objects_dir`; citation target type; event isolation;
      parse timestamps; space/model check; remove `turn_id` branch; normalized
      `min_score`. (M-050…M-059)
- [x] 4.2 Cache embedder + n-gram backend with invalidation; batch N+1 lookups;
      FTS candidate search; bound `retrieval_run`. (P-071…P-075)
- [x] 4.3 Regression tests: deleted segment not searchable; migration failure
      leaves no DDL/version; rollback-on-retry. Two-connection contention tests
      remain owned by the open `harden-sqlite-write-contention` change (task 1.3)
      — not duplicated here. (M-050, M-051, geomemory TEST-01/02)
- [x] 4.4 Stop the unbounded `retrieval_run` JSON audit log and the per-query
      auto-download check; retired the RTree spatial prefilter from candidate
      selection with a documented rationale; spike converging facade retrieval
      onto `SearchService` adapters with golden fixtures. (geomemory DEBT-01, DIRECTION-01)

## 5. Verification, DX, docs (T-081…T-083, X-084…X-093)

- [x] 5.1 CI: `geomemorytest/` suite with `xfail(strict=True)` baseline;
      characterisation lint/mypy gate that fails only on new violations;
      `pip-audit` + `pnpm audit --audit-level=high`; one shared conda env;
      add the declared Python floor to the matrix. (T-081, T-082, CI-01…03, DEP-02)
- [x] 5.2 Remove `httpx2`; add license metadata to three libs. (DEP-01, DEP-03)
- [x] 5.3 Align env name, README `cd`, `.env.example`, pnpm pin, `wait -n`. (X-084…X-088)
- [x] 5.4 Correct `SPEC_WEB.md`, sample-pipeline spec, privacy/auth claims,
      `GEOFONT_STATE_PATH` alias + prefix documentation. (X-089…X-092, DOC-05)
- [x] 5.5 Add a real-rasterio windowing regression test for the download/clip
      path (scene-CRS bounds → `from_bounds` → windowed read + transform). (T-083)

## 6. Final gate

- [ ] 6.1 All commands above green; `git status` shows only in-scope files;
      audit rows for these findings marked REJECTED/DONE in `plans/AUDIT-2026-11-22.md`.
