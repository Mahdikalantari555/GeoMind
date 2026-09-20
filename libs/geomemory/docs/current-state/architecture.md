# System Architecture — Current State

Snapshot: 2026-09-21 · `libs/geomemory` v0.1.0 alpha
Normative source of truth: [`../../openspec/specs/`](../../openspec/specs/)
Comprehensive summary: [`../library-capabilities.md`](../library-capabilities.md)

## 1. Runtime topology

GeoMemory is an **in-process Python library**. The default deployment has no GeoMemory HTTP server, daemon, or required external database.

```
┌──────────────────────────────────────────────────────────────┐
│ Consumers                                                    │
│ CLI (geomemory) · Streamlit UI · notebooks · gateway/web     │
└───────────────┬──────────────────────────────────────────────┘
                │ public API only (geomemory.GeoMemory)
┌───────────────▼──────────────────────────────────────────────┐
│ Facade: GeoMemory (core/workspace.py)                        │
│ open/create · collections · ingest · search · ask            │
│ build_index · feedback · review · export · benchmark         │
│ pipeline_stats · traverse · temporal/entity helpers          │
├──────────────────────────────────────────────────────────────┤
│ Domain modules                                               │
│ core/ models, facade, config, events, hashing, registries    │
│ ingest/ loaders, chunkers, pipeline, job queue               │
│ embeddings/ ONNX, hashing, llama.cpp, OLMoEarth, hub         │
│ index/ sqlite-vec, LanceDB, Qdrant, numpy, manifests         │
│ retrieval/ parser, fusion, filters, search service           │
│ qa/ chat, prompts, citations, abstention, LLM backends       │
│ rs/ raster reader/tiler/preview/spectral, vector reader      │
│ feedback/ candidate memory, scoring, review, exporters       │
│ eval/ metrics, runner, pipeline stats, run store             │
│ services/ index, ingestion, search, chat, doctor, wrappers   │
│ storage/ SQLite connect/migrate, repositories, object store  │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
        workspace/geomemory.db     workspace/objects/
        SQLite WAL + FTS5 + RTree  ab/cd/<sha256>
        + optional sqlite-vec
```

External model assets are loaded lazily from paths recorded in workspace settings or resolved through the embedding model hub — never hardcoded.

## 2. Architectural style

| Pattern | Where | Notes |
|---|---|---|
| Facade | `core/workspace.py` → `GeoMemory` | Single public entry point |
| Protocol-based backends | text/vision embedders, vector/storage backends, LLM backend | Swap implementations without changing callers |
| Registry | loader/chunker/embedder/backend registries | In-process plugin points |
| Repository | `storage/repositories/` | Typed row ↔ model mapping over parameterized SQL |
| Event bus | `core/events.py` | In-process extension point |
| DB-backed job model | `ingest/job_queue.py` + `job` table | Pending/running/completed/failed/cancelled states |
| Content-addressed storage | `storage/object_store.py` | SHA-256 immutable blobs |

## 3. Current canonical paths

### 3.1 Lightweight text/dense path

The current canonical torch-free path is:

1. Ingest segments into SQLite/FTS5.
2. Embed segments with ONNX `Xenova/all-MiniLM-L6-v2`.
3. Store vectors in sqlite-vec `vec0` virtual tables per embedding space.
4. Persist `embedding_record` metadata and an index manifest.
5. Search with FTS5 + sqlite-vec and fuse with RRF.

### 3.2 Pluggable alternatives

- Vector storage: `SqliteVecBackend`, `LanceBackend`, `QdrantBackend`, persisted `VectorBackend`, `NumpyBackend`.
- Text embeddings: ONNX, hashing fallback, legacy llama.cpp GGUF, provider stubs.
- Vision embeddings: OLMoEarth torch path or placeholder when unavailable.
- PDF parsing: OpenDataLoader PDF or PyMuPDF fallback.
- LLM generation: llama.cpp, OpenAI-compatible API, or null/abstaining backend.

## 4. Layer rules

- Consumers should use the public API exported from `geomemory/__init__.py`.
- Heavy optional dependencies are imported lazily where practical.
- Embedding spaces are isolated per modality and model.
- Domain objects are Pydantic v2 models.
- Content identity is SHA-256; revisions are immutable.
- Candidate memories are reviewable and separated from authoritative knowledge.
- Superseded candidate memories are excluded from default candidate search.
- SQL access uses bound parameters through repositories and storage modules.

## 5. Concurrency and operations

- SQLite runs in WAL mode with foreign keys enabled.
- The default model is one writer and concurrent readers.
- Ingestion can be synchronous through the facade or represented as pending jobs through services; there is no built-in background worker process.
- `doctor` reports environment, optional dependencies, database readability, LLM/Qdrant/PDF/vision/embedding state, and workspace integrity.

## 6. Spec/implementation boundary

`openspec/specs/` is normative. This document describes implementation status. Where the spec and implementation differ — notably LanceDB/sentence-transformers versus the current ONNX/sqlite-vec lightweight path — the comprehensive guide records the drift explicitly.

## 7. What is not built into the library

- No built-in multi-tenant HTTP server or authentication system.
- no distributed ingestion or cluster scheduler.
- No automatic background worker consuming jobs.
- No automatic entity extraction/NER; entity linking uses seeded aliases.
- No automatic temporal backfill; `observed_at` is caller-supplied.
