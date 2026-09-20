# Deployment Architecture — Current State

Snapshot: 2026-09-21 · `libs/geomemory` v0.1.0 alpha
Normative source of truth: [`../../openspec/specs/`](../../openspec/specs/)
Comprehensive summary: [`../library-capabilities.md`](../library-capabilities.md)

## Model

**Local-first, single-machine, single-process.** GeoMemory ships as a Python library + CLI + optional Streamlit reference UI + Docker/compose assets.

```
┌────────────────────────────────────────────────────────────────┐
│ conda env "geospatial" (Python ≥3.10)                          │
│ ├─ pip install -e libs/geomemory                               │
│ ├─ optional extras: docs, rs, vector, lancedb, vision,         │
│ │   llamacpp, opendataloader, ui, dev                          │
│ ├─ model assets loaded lazily from settings/hub               │
│ └─ processes:                                                  │
│      geomemory <cmd>        (short-lived CLI process)          │
│      streamlit run apps/dashboard/app.py   (single-user UI)   │
│                                                                 │
│  workspace/ directory = the entire deployment state             │
│    workspace.yaml · geomemory.db (+WAL) · objects/ · indexes/   │
└────────────────────────────────────────────────────────────────┘
```

## Container deployment

The library ships Docker assets:

- `Dockerfile` with multiple targets: `core`, `docs`, `rs`, `vector`, `vision`, `llamacpp`, `ui`.
- `docker-compose.yml` starts Qdrant plus the GeoMemory UI with persistent volumes.
- `docker-compose.dev.yml` bind-mounts `src/` for development.

## Configuration surface

- `workspace.yaml` (via `WorkspaceSettings`): model paths, offline flag, language (`en`/`fa`), workspace name, LLM provider, embedding provider, vector backend, vision path, and PDF parser preference.
- `GEOMEMORY_DASHBOARD_ROOT`: dashboard default workspace path.
- Environment overrides documented in `core/config.py`.
- No env-based secrets; nothing phones home (offline by default).

## Data durability and backup

- All state is plain files → backup = copy the workspace directory.
- SQLite WAL mode gives crash-safe commits; `doctor` runs integrity checks.
- Blobs are content-addressed and immutable → safe to rsync/dedupe.
- No automated backup, retention, or migration tooling exists yet.

## Scale envelope

| Dimension | Envelope | Constraint |
|---|---|---|
| Corpus size | ~10³–10⁴ segments comfortable | dense search is brute-force without ANN; FTS5 fine beyond that |
| Concurrency | 1 writer, N readers (WAL) | single user assumption |
| Assets per collection | unbounded logically | listing APIs paginate poorly at large N |
| Model footprint | few GB | loaded lazily per process; no model server/shared cache |

## Operational entry points

- `geomemory doctor [-w PATH]` — dependency, DB, settings, LLM, Qdrant, PDF, vision, embedding diagnostics.
- `pytest libs/geomemory/tests` — unit/integration/golden/e2e suites; markers gate selection.
- `geomemory eval run|stats|rebuild|compare` — benchmark and regression checks.

## Explicit non-goals

- Multi-tenant hosting, auth, TLS — absent by design (local research tool).
- Horizontal scaling / distributed ingestion — not addressed.
- GPU orchestration — CPU defaults only.

## Candidate future deployment shapes

1. Library remains canonical; add optional FastAPI/MCP wrapper for agent access.
2. Background worker consuming the existing `job` table for async ingestion.
3. Optional S3/local-dir blob backend behind `ObjectStore` interface.