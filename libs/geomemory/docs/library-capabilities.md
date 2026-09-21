# GeoMemory Library Capabilities — Comprehensive Guide

Status: current synthesis of `libs/geomemory`
Source of truth: [`openspec/specs/`](../openspec/specs/)
Audience: contributors, gateway/web integrators, researchers, and maintainers

> **Normative precedence**
> `libs/geomemory/openspec/specs/` is the authoritative source of truth for GeoMemory behavior.
> This document summarizes and organizes those specs. If this guide conflicts with a spec, the spec wins.
> Where the current implementation intentionally differs or lags behind a spec, the difference is called out under **Implementation status / drift**.

## 1. What GeoMemory is

GeoMemory is a local-first, file-first Python library and CLI for turning heterogeneous research sources into a searchable, citation-grounded, spatiotemporal memory.

It supports:

- Documents, code, PDFs, GeoJSON, Shapefiles, GeoTIFF scenes, and raster/vector assets.
- Hybrid sparse + dense retrieval with rank fusion.
- Spatial, temporal, sensor, and collection filters.
- Grounded QA with citations, abstention, and conversation/audit persistence.
- Candidate memories, review queues, dataset exports, and evaluation benchmarks.
- Temporal belief history, entity profiles, and research timelines.
- Optional pluggable vector backends and optional vision embeddings.
- A CLI, a Streamlit reference UI, Docker/compose assets, and a reusable Python facade.

The library is in-process by default. It does not require an external database, vector server, model server, or network service. Optional Qdrant and LLM API integrations are opt-in.

## 2. Capability catalog

The following capability specs live under [`openspec/specs/`](../openspec/specs/). Each section below summarizes the normative contract and the current implementation surface.

| Capability | Spec | Primary purpose |
|---|---|---|
| Workspace Management | [`workspace-management`](../openspec/specs/workspace-management/spec.md) | Create/open workspaces, persist settings, manage collections, run diagnostics |
| Ingestion | [`ingestion`](../openspec/specs/ingestion/spec.md) | Convert files/bytes into immutable revisions, segments, and spatial records |
| PDF Ingestion | [`pdf-ingestion`](../openspec/specs/pdf-ingestion/spec.md) | Parse PDFs with high-quality or fallback parser selection and bbox locators |
| Storage Architecture | [`storage-architecture`](../openspec/specs/storage-architecture/spec.md) | Local-first SQLite + vector backend storage model |
| Storage & Persistence | [`storage-persistence`](../openspec/specs/storage-persistence/spec.md) | SQLite WAL/FK, migrations, FTS/RTree, object store, repositories |
| Search & Retrieval | [`search-retrieval`](../openspec/specs/search-retrieval/spec.md) | Hybrid search, query parsing, filters, auditability, index lifecycle |
| Sentence Transformer Embeddings | [`sentence-transformer-embeddings`](../openspec/specs/sentence-transformer-embeddings/spec.md) | Optional dense text embeddings with model/space isolation |
| Qdrant Vector Backend | [`qdrant-vector-backend`](../openspec/specs/qdrant-vector-backend/spec.md) | Optional server-mode dense retrieval |
| Vision Embedding | [`vision-embedding`](../openspec/specs/vision-embedding/spec.md) | Optional OLMoEarth image embeddings |
| Grounded QA | [`grounded-qa`](../openspec/specs/grounded-qa/spec.md) | Evidence-grounded answers, citations, abstention, provider selection |
| Remote Sensing | [`remote-sensing`](../openspec/specs/remote-sensing/spec.md) | Raster/vector ingestion, spatial metadata, spectral indices |
| Feedback & Evaluation | [`feedback-evaluation`](../openspec/specs/feedback-evaluation/spec.md) | Feedback capture, dataset review/export, benchmark metrics |
| Pipeline Statistics | [`pipeline-stats`](../openspec/specs/pipeline-stats/spec.md) | Stable ingestion statistics schema |
| Eval Datasets | [`eval-datasets`](../openspec/specs/eval-datasets/spec.md) | In-repo benchmark dataset layout and query contract |
| Run Storage | [`run-storage`](../openspec/specs/run-storage/spec.md) | Immutable benchmark run artifacts |
| Run Comparison | [`run-comparison`](../openspec/specs/run-comparison/spec.md) | Diff two runs and detect regressions |
| Candidate Memory Store | [`candidate-memory-store`](../openspec/specs/candidate-memory-store/spec.md) | Temporal fields and as-of reads for candidate memories |
| Evolutionary Memory | [`evolutionary-memory`](../openspec/specs/evolutionary-memory/spec.md) | Governed candidate memory lifecycle, profiles, timelines, supersession |
| Temporal Memory | [`temporal-memory`](../openspec/specs/temporal-memory/spec.md) | Point-in-time belief reconstruction |
| Entity Profiles | [`entity-profiles`](../openspec/specs/entity-profiles/spec.md) | Alias-based entity views and gateway response contract |
| Research Timelines | [`research-timelines`](../openspec/specs/research-timelines/spec.md) | Project-scoped chronological candidate memory views |
| Docker Deployment | [`docker-deployment`](../openspec/specs/docker-deployment/spec.md) | Reproducible image/compose stack |

## 3. Core architecture

### 3.1 Runtime topology

GeoMemory is an in-process Python library. Consumers import the public API or invoke the CLI.

Primary consumers:

- Python applications via `import geomemory`.
- `geomemory` CLI.
- Streamlit reference UI under `apps/dashboard/` and legacy `apps/app.py`.
- External GeoFoundation gateway/web stack, which consumes library capabilities through server-side integration.

Primary layers:

1. **Public API / facade** — `geomemory.GeoMemory` in `src/geomemory/core/workspace.py`.
2. **Domain modules** — `core`, `ingest`, `embeddings`, `index`, `retrieval`, `qa`, `rs`, `feedback`, `eval`, `knowledge`, `services`, `storage`.
3. **Storage** — SQLite database, FTS5/RTree/sqlite-vec virtual tables, migrations, repositories, and content-addressed object store.
4. **Optional integrations** — LanceDB, Qdrant, ONNX model hub, PyMuPDF/OpenDataLoader, rasterio/geopandas/shapely, llama.cpp, torch/OLMoEarth, Streamlit.

### 3.2 Architectural invariants

These invariants are normative across capability specs and implementation:

- **Local-first / offline by default** — no mandatory external service; network use is opt-in and guarded.
- **File-first workspace** — a workspace directory is portable and backup-friendly.
- **SQLite as structured source of truth** — metadata, segments, candidate memories, relations, QA audit rows, and migration state.
- **Content identity** — SHA-256 raw-byte hashing with immutable revisions and deduplication.
- **Provenance** — answer → citation → segment/locator → asset revision/hash → object-store bytes.
- **Embedding-space isolation** — text and vision spaces are never mixed; model/space changes require rebuild.
- **Protocol-based backends** — embedders, vector backends, loaders, chunkers, and LLM backends are replaceable.
- **Parameterized SQL** — repositories and storage code use bound parameters, not string interpolation.
- **Single-writer SQLite model** — WAL permits concurrent readers with one writer; multi-process retry behavior remains an operational concern.
- **Optional heavy dependencies** — raster, vector, PDF, vision, llama.cpp, Qdrant, and UI dependencies stay behind extras and lazy imports where practical.

### 3.3 Public API surface

`geomemory/__init__.py` exports:

- Facade: `GeoMemory`.
- Exceptions: `GeoMemoryError`, `WorkspaceNotFoundError`, `CollectionNotFoundError`, `AssetNotFoundError`, `UnsupportedFormatError`, `DatabaseError`, `ModelNotLoadedError`, `NetworkDisabledError`, `EmbeddingUnavailableError`, `AbstentionError`.
- Models: `Workspace`, `Collection`, `Asset`, `AssetRevision`, `Segment`, `EmbeddingRecord`, `Entity`, `CandidateMemory`, `KnowledgeChangeProposal`, `Job`, `RetrievalRun`, `Answer`, `Citation`, `SearchFilters`, `SearchRequest` where exported through model modules, `SearchHit`, `SearchResult`, `SpatialFilter`, `TemporalFilter`, `QAResult`.

Important facade operations include:

| Area | Methods |
|---|---|
| Workspace | `open`, `create`, `close`, context manager, `settings`, `update_settings` |
| Collections | `create_collection`, `list_collections`, `get_collection`, `archive_collection` |
| Ingestion | `ingest` |
| Retrieval | `search`, `traverse`, `_expand_relation_context` internally |
| QA | `ask` |
| Indexing | `build_index`, `rebuild_index` |
| Vision | `image_index`, `search_images` |
| Feedback | `record_feedback`, `get_review_queue`, `review_example`, `export_dataset` |
| Evaluation | `run_benchmark`, `pipeline_stats` |
| Inspection | `list_assets`, `inspect`, `stats` |

The public facade is the stability boundary. Internal modules may evolve; consumers should depend on `geomemory.GeoMemory` and exported models/exceptions.

## 4. Installation, settings, and environment

### 4.1 Base install

The canonical lightweight install is torch-free:

```bash
conda run -n geospatial pip install -e libs/geomemory
```

Current base dependencies are:

- `pydantic>=2.0`
- `numpy>=1.24`
- `click>=8.0`
- `PyYAML>=6.0`
- `onnxruntime>=1.18`
- `tokenizers>=0.15`
- `huggingface-hub>=0.23`
- `sqlite-vec>=0.1.6`

### 4.2 Optional extras

| Extra | Packages / purpose |
|---|---|
| `docs` | PyMuPDF and python-docx for document parsing support |
| `rs` | rasterio, shapely, geopandas, Pillow for remote sensing |
| `vector` | qdrant-client for server-mode vector backend |
| `lancedb` | pylancedb for embedded LanceDB backend |
| `vision` | torch, Pillow, olmoearth-pretrain-minimal for OLMoEarth vision embeddings |
| `llamacpp` | llama-cpp-python for legacy GGUF inference |
| `opendataloader` | high-quality PDF parser requiring Java runtime |
| `ui` | Streamlit reference UI |
| `dev` | pytest, pytest-cov, mypy, ruff, types-PyYAML |

### 4.3 Environment overrides

Documented environment overrides include:

| Variable | Setting |
|---|---|
| `GEOMEMORY_EMBEDDING_PROVIDER` | `embedding_provider` (`onnx/openai/voyage/custom/hashing/llama-cpp/cloudflare`) |
| `GEOMEMORY_EMBEDDING_BACKEND` | deprecated backend alias |
| `GEOMEMORY_ONNX_MODEL` | `onnx_model_name` |
| `GEOMEMORY_CLOUDFLARE_ACCOUNT_ID` | `cloudflare_account_id` |
| `GEOMEMORY_CLOUDFLARE_API_TOKEN` | `cloudflare_api_token` |
| `GEOMEMORY_CLOUDFLARE_MODEL_ID` | `cloudflare_model_id` |
| `GEOMEMORY_EMBEDDING_ROOT` | embedding model hub root |
| `GEOMEMORY_VECTOR_BACKEND` | vector backend selection |
| `GEOMEMORY_QDRANT_URL` | Qdrant URL |
| `GEOMEMORY_ST_MODEL` | deprecated sentence-transformers model name |
| `GEOMEMORY_VISION_PATH` | vision checkpoint path |
| `GEOMEMORY_LLM_*` | LLM provider/base URL/key env/model/context window |

Offline mode refuses network downloads and surfaces actionable errors such as `NetworkDisabledError` or `EmbeddingUnavailableError`.

## 5. Workspace, storage, and schema

### 5.1 Workspace layout

A GeoMemory workspace is a self-contained directory:

```text
workspace/
├── .geomemory
├── workspace.yaml
├── geomemory.db
├── objects/<aa>/<bb>/<sha256>
└── indexes/<space_id>/manifest.json
```

The database contains structured state. The object store contains raw content-addressed bytes. Index artifacts and manifests live beside the database.

### 5.2 Database and virtual tables

Current schema is versioned. The initial schema is version 1; migrations extend it. Migration 6 is the current temporal/entity candidate-memory migration.

Core tables include:

- Workspace and collections: `workspace`, `collection`.
- Assets and revisions: `asset`, `asset_revision`.
- Segments and lexical search: `segment`, `segments_fts`.
- Spatial index: `spatial_entity`, `spatial_index` RTree.
- Remote sensing: `raster_scene`, `raster_tile`, `vector_layer`.
- Observations and graph: `observation`, `embedding_record`, `entity`, `relation`.
- Conversations and QA: `conversation`, `turn`, `retrieval_run`, `answer`, `citation`.
- Feedback and datasets: `feedback_event`, `dataset_example`, `job`.
- Candidate memory and evolution: `candidate_memory`, `knowledge_change_proposal`, `provenance_chain`.
- Migration registry: `schema_migration`.

### 5.3 Candidate memory schema

`candidate_memory` carries the research belief layer:

- `id`, `content`, `memory_type`
- `source_feedback_ids`, `confidence_score`, `state`, `author`
- `audit_trail`, `created_at`, `updated_at`
- `observed_at`
- `superseded_by` with self-FK `ON DELETE SET NULL`
- `project`

Allowed `memory_type` values:

```text
fact | correction | annotation | preference | decision | hypothesis | method | dataset_event | episodic | working
```

Allowed lifecycle states:

```text
proposed | supported | verified | rejected
```

Indexes include state, score, and `(id, observed_at DESC)`.

### 5.4 Migration behavior

Migrations are version-registered and idempotent. The temporal migration:

- Adds `observed_at`, `superseded_by`, and `project`.
- Widens `memory_type` rather than removing auditability constraints.
- Rebuilds `candidate_memory` because SQLite cannot alter a CHECK constraint.
- Preserves existing candidate rows and provenance-chain foreign keys.
- Recreates candidate indexes.

## 6. Capability details

### 6.1 Workspace management

Spec: [`workspace-management`](../openspec/specs/workspace-management/spec.md)

Normative behavior:

- `GeoMemory.create(path, config)` creates `workspace.yaml`, `geomemory.db`, and `objects/`.
- Creation refuses to clobber an existing valid workspace.
- `GeoMemory.open(path)` raises `WorkspaceNotFoundError` for invalid paths.
- Settings persist to YAML and are updatable through the facade.
- Collections are workspace-scoped; assets belong to exactly one collection.
- `doctor` reports dependency, database, settings, LLM, Qdrant, PDF parser, vision, and embedding state without mutating data.
- LLM settings are additive and backward-compatible.
- API key material is never written to `workspace.yaml`, logs, or database rows; it is read at use time from the named environment variable.

### 6.2 Ingestion

Spec: [`ingestion`](../openspec/specs/ingestion/spec.md)

Normative behavior:

- Accepts `str`, `Path`, or raw `bytes`.
- Rejects unknown collections before writes.
- Computes SHA-256 and short-circuits duplicate revisions.
- Routes by detected MIME/kind to text, code, PDF, GeoJSON, GeoTIFF, and Shapefile loaders.
- Produces typed segments: `paragraph`, `table`, `formula`, `code_unit`, `heading`, `cell`.
- Raises `UnsupportedFormatError` for unresolvable formats.
- Creates immutable asset revisions with hash, MIME, size, and parser version.
- Persists raster scenes/tiles or vector layers plus RTree entries for spatial sources.
- Represents ingestion as a `Job`; service submission can enqueue pending work.
- Supports PDF parser selection and precise PDF bbox locators.
- Registers Shapefile support with clear missing-dependency errors.

### 6.3 PDF ingestion

Spec: [`pdf-ingestion`](../openspec/specs/pdf-ingestion/spec.md)

Normative behavior:

- Prefer `opendataloader-pdf` when installed and Java is available.
- Fall back to PyMuPDF when the high-quality parser or Java runtime is unavailable.
- Allow workspace settings to force a specific parser subject to availability.
- Preserve page, bbox, element id, and element type in locators for precise citation.

### 6.4 Storage architecture

Spec: [`storage-architecture`](../openspec/specs/storage-architecture/spec.md)

Normative behavior:

- Use a self-contained workspace with SQLite as source of truth.
- Keep large binaries and raw vectors out of SQLite where the architecture calls for backend storage.
- Use FTS5 for lexical search and lightweight spatial metadata for bbox/AOI filtering.
- Keep raster files external to the database while persisting metadata.
- Provide pluggable vector backends behind protocols.
- Keep embedding spaces isolated by modality and model.
- Preserve local-first operation with no mandatory Redis, Elasticsearch, MongoDB, Qdrant, Pinecone, or PostgreSQL service.

**Implementation status / drift:** The lightweight current implementation uses ONNX + sqlite-vec as the canonical torch-free dense path. The storage-architecture spec names LanceDB as the default vector backend and sentence-transformers as the default text embedding family. The codebase supports both directions: sqlite-vec/LanceDB/Qdrant/numpy backends and ONNX/hashing/llama-cpp/provider stubs. Treat the spec as the normative target and record this as active storage/embedding drift to resolve.

### 6.5 Storage and persistence

Spec: [`storage-persistence`](../openspec/specs/storage-persistence/spec.md)

Normative behavior:

- Open SQLite in WAL mode with foreign keys enabled.
- Apply versioned migrations through `schema_migration`.
- Keep `segments_fts` synchronized with `segment` via triggers.
- Maintain RTree spatial indexing through the `spatial_entity` mapping table.
- Store raw bytes once by SHA-256 in `objects/<aa>/<bb>/<hash>`.
- Use typed repositories with parameterized SQL.
- Support project/memory-type candidate listing with stable descending observation order and pagination.

### 6.6 Search and retrieval

Spec: [`search-retrieval`](../openspec/specs/search-retrieval/spec.md)

Normative behavior:

- Combine sparse FTS5 and dense vector results using RRF by default.
- Support selectable `sparse`, `dense`, and linear-fusion modes.
- Parse queries into filters and intent plans.
- Post-filter by spatial bbox, temporal window, sensor, and collection scope.
- Deduplicate and apply per-document diversity caps.
- Truncate to `top_n`.
- Persist a `RetrievalRun` with query, plan, filters, config, candidates/results, and latency.
- Build/rebuild vector indexes per embedding space with manifests containing space, model, dimension, and checksums.
- Never mix vectors from different embedding spaces.

Current implementation notes:

- The canonical fusion path is `retrieval/fusion.rrf_fuse` plus `retrieval/search_service.apply_hit_filters`.
- Dense backends include sqlite-vec, LanceDB, Qdrant, persisted vector backend, and numpy fallback.
- Candidate memories are merged with authoritative hits after ranking, with superseded candidates excluded by default.

### 6.7 Text embeddings and embedding spaces

Specs:

- [`sentence-transformer-embeddings`](../openspec/specs/sentence-transformer-embeddings/spec.md)
- [`storage-architecture`](../openspec/specs/storage-architecture/spec.md)

Normative behavior:

- Text embeddings are produced behind a text-embedder contract.
- Sentence-transformers mode returns L2-normalized dense vectors and supports alternative multilingual models.
- e5-family inputs require `query:`/`passage:` prefixes; models without prefix requirements pass through unchanged.
- Each model maps to one stable space id; changing model forces a new space and rebuild.
- Index manifests record model id, dimension, space id, and build metadata.
- Semantic search detects model/space mismatch and warns instead of silently mixing vectors.
- Missing optional dependencies produce actionable errors naming the required extra.

Current implementation notes:

- Canonical lightweight path is `ONNXEmbeddingProvider` with `Xenova/all-MiniLM-L6-v2`, 384 dimensions, quantized ONNX, mean pooling, and L2 normalization.
- `HashingTextEmbedder` remains a dependency-free fallback.
- `LlamaCppTextEmbedder` remains a legacy GGUF path.
- Provider stubs exist for OpenAI, Voyage, and custom endpoints.
- `doctor` reports ONNX, tokenizer, hub, and sqlite-vec availability.

### 6.8 Vector backends

Specs:

- [`qdrant-vector-backend`](../openspec/specs/qdrant-vector-backend/spec.md)
- [`storage-architecture`](../openspec/specs/storage-architecture/spec.md)

Normative behavior:

- Vector backend selection is configuration-driven.
- Qdrant mode uses one collection per embedding space.
- Backends support upsert, search, delete, count, and rebuild behavior.
- Qdrant search honors `top_k` and cosine ranking.
- Unreachable Qdrant servers fail loudly; no silent local fallback fabricates results.
- Doctor reports Qdrant client installation and server reachability.

Current implementation notes:

- `SqliteVecBackend` stores vectors in per-space `vec0` virtual tables inside SQLite, keeping backup simple.
- `LanceBackend`, `QdrantBackend`, `VectorBackend`, and `NumpyBackend` sit behind the storage/retrieval backend protocols.
- `IndexService` embeds segments through the configured provider, writes `EmbeddingRecord` rows, upserts vectors, and writes manifests.

### 6.9 Vision embedding

Spec: [`vision-embedding`](../openspec/specs/vision-embedding/spec.md)

Normative behavior:

- When configured and `[vision]` is installed, load OLMoEarth v1.2 Nano directly from native PyTorch weights on CPU.
- Accept image paths, bytes, or PIL images.
- Return `(N, D)` float32 L2-normalized vectors.
- Report a stable vision space id distinct from all text spaces.
- Auto-download only when permitted by offline settings; otherwise use placeholder or actionable error behavior.
- Fail loudly on missing or invalid checkpoints.
- Report torch availability and checkpoint existence in Doctor.

Current implementation notes:

- `OlmoEarthVisionEmbedder` is the real torch path.
- `PlaceholderVisionEmbedder` is used when no checkpoint is configured or torch is unavailable.
- Vision remains opt-in and is not required for text/document workflows.

### 6.10 Grounded QA

Spec: [`grounded-qa`](../openspec/specs/grounded-qa/spec.md)

Normative behavior:

- Answer using retrieved workspace evidence and a mode-appropriate prompt.
- Support `grounded_qa`, `research`, and `code` modes.
- Map inline `[n]` citations to source segments and validate them.
- Persist conversation, turns, answer, model id, prompt hash, abstention flag, and citations.
- Abstain when evidence is insufficient or no LLM backend is configured.
- Select LLM backend from settings: `null`, `llamacpp`, or OpenAI-compatible `api`.
- Preserve baseline behavior when `llm_provider` is unset.
- Use stdlib HTTP for OpenAI-compatible chat completions.
- Abstain with clear reasons for missing API key, offline mode, or HTTP failure.
- Derive QA context budget from `llm_context_window`; use the same window for local llama.cpp context size.

### 6.11 Remote sensing

Spec: [`remote-sensing`](../openspec/specs/remote-sensing/spec.md)

Normative behavior:

- Ingest GeoTIFF scenes with sensor, bands, EPSG CRS, bbox, transform, dtype, nodata, dimensions, and resolution.
- Persist raster scenes and tiles with spatial index coverage.
- Compute NDVI and EVI as pure-numpy functions with shape validation.
- Support generic index computation and band-mapping validation.
- Ingest GeoJSON/vector sources with OGC geometry type, CRS, feature count, and footprint.
- Filter scenes/layers by bbox, acquisition time, and sensor through normal search filters.
- Keep rasterio/geopandas/shapely/Pillow behind lazy imports and clear missing-extra errors.

### 6.12 Feedback, candidate memory, and evolutionary memory

Specs:

- [`feedback-evaluation`](../openspec/specs/feedback-evaluation/spec.md)
- [`evolutionary-memory`](../openspec/specs/evolutionary-memory/spec.md)
- [`candidate-memory-store`](../openspec/specs/candidate-memory-store/spec.md)

Normative behavior:

- Record raw feedback events append-only.
- Convert feedback into dataset examples with task typing and source linkage.
- Deduplicate equivalent examples before review.
- Move examples through `pending → accepted | rejected` with reviewer and timestamp.
- Export accepted examples as `rag_eval`, `qa_eval`, `sft`, and `preference` datasets with cards.
- Keep candidate memories separate from authoritative knowledge until reviewed.
- Preserve audit trails and reversibility.
- Exclude rejected candidates from retrieval and ranking.
- Store candidate temporal fields: `observed_at`, `superseded_by`, and `project`.
- Return the latest as-of revision in a supersession chain.
- Exclude superseded candidates from search by default; include them only on explicit opt-in.

### 6.13 Temporal memory

Specs:

- [`temporal-memory`](../openspec/specs/temporal-memory/spec.md)
- [`candidate-memory-store`](../openspec/specs/candidate-memory-store/spec.md)

Normative behavior:

- `observed_at` means when a belief was true/held; `created_at` means when the system learned it.
- Unset `observed_at` falls back to `created_at` only at read/query time.
- The stored `observed_at` remains null until explicitly supplied.
- As-of queries return the latest revision whose effective observation time is at or before the requested time.
- As-of queries return no revision when every revision is newer than the requested time.

### 6.14 Entity profiles

Spec: [`entity-profiles`](../openspec/specs/entity-profiles/spec.md)

Normative behavior:

- Match candidate content against a configurable seeded alias index using case-insensitive substring matching.
- Keep all links when aliases collide.
- Return entity name/kind, current beliefs, full supersession history, and related entity names.
- Return an empty profile at the service boundary for unknown entities.
- Related entities include relation-table neighbors and alias co-mentions.
- Gateway contract: `GET /api/v1/memory/entities/{entity_name}` returns 200 for known entities and 404 for unknown entities.

Current implementation notes:

- `EntityProfileService` reads `workspace.settings.entity_alias_index` from workspace settings, with a seeded default alias list.
- The service joins candidate memories to entity/relation data without automatic NER.

### 6.15 Research timelines

Spec: [`research-timelines`](../openspec/specs/research-timelines/spec.md)

Normative behavior:

- Expose `GET /api/v1/research/timeline`.
- Require `project`.
- Accept optional comma-separated `type`, optional `as_of`, `offset` default 0, and `limit` default 50.
- Filter by project, memory type, and observation time.
- Order by effective `observed_at` descending.
- Return the requested page and total matching count.

Current implementation notes:

- `ResearchTimelineService` delegates to `CandidateMemoryRepository.list_by_project`.
- The gateway router translates comma-separated types and serializes Pydantic candidate memories to JSON.

### 6.16 Evaluation framework

Specs:

- [`feedback-evaluation`](../openspec/specs/feedback-evaluation/spec.md)
- [`pipeline-stats`](../openspec/specs/pipeline-stats/spec.md)
- [`eval-datasets`](../openspec/specs/eval-datasets/spec.md)
- [`run-storage`](../openspec/specs/run-storage/spec.md)
- [`run-comparison`](../openspec/specs/run-comparison/spec.md)

Normative behavior:

- Run benchmarks over production ingestion, retrieval, and QA paths.
- Compute retrieval metrics: recall@k, precision@k, MRR@k, nDCG@k.
- Compute QA metrics: abstention accuracy/rate, citation correctness, and faithfulness proxy.
- Persist per-query rows with retrieved ids, scores, metadata, and response.
- Recognize datasets under `geomemory-evals/datasets/<name>/` containing `queries.yaml`.
- Accept only production-supported source formats and fail clearly on unsupported files.
- Emit stable eight-field pipeline stats: `files`, `documents`, `chunks`, `embeddings`, `entities`, `relations`, `duration_seconds`, `storage_bytes`.
- Write immutable run artifacts under `geomemory-evals/runs/<dataset>/<timestamp>/`.
- Compare two runs for statistics drift and per-query retrieval differences.
- Exit non-zero when runs differ; exit zero when equivalent.

CLI surface:

```bash
geomemory eval run BENCHMARK.jsonl
geomemory eval stats DATASET
geomemory eval rebuild DATASET
geomemory eval compare RUN_A RUN_B
```

### 6.17 Docker deployment

Spec: [`docker-deployment`](../openspec/specs/docker-deployment/spec.md)

Normative behavior:

- Provide reproducible images and a compose stack.
- Provide CLI and UI targets.
- Start Qdrant and the GeoMemory UI with one command.
- Persist Qdrant storage, workspace data, and Hugging Face cache in named volumes.
- Configure behavior through documented environment variables with sensible defaults.

Current implementation notes:

- `Dockerfile` provides multiple targets: `core`, `docs`, `rs`, `vector`, `vision`, `llamacpp`, and `ui`.
- `docker-compose.yml` starts Qdrant plus GeoMemory UI and defines `qdrant_storage`, `workspace_data`, and `hf_cache` volumes.
- `docker-compose.dev.yml` bind-mounts `src/` for development.

## 7. CLI and consumer surfaces

### 7.1 CLI

Current CLI commands:

```text
geomemory init PATH
geomemory ingest SOURCE --collection NAME
geomemory index build|rebuild|reindex
geomemory search QUERY
geomemory ask QUESTION
geomemory chat
geomemory inspect ASSET_ID
geomemory eval run|stats|rebuild|compare
geomemory feedback export|review
geomemory doctor
geomemory reindex
geomemory app
```

CLI imports are lazy so startup does not pull heavy optional dependencies.

### 7.2 Gateway integration

The GeoFoundation gateway consumes GeoMemory server-side. Relevant additive routes from the temporal/entity specs are:

```http
GET /api/v1/memory/entities/{entity_name}
GET /api/v1/research/timeline?project=X&type=Y&as_of=Z&offset=0&limit=50
```

The library itself remains in-process; these are integration contracts, not a built-in GeoMemory HTTP server.

### 7.3 Dashboard

The Streamlit reference UI consumes only the public facade. It is optional and not part of the core library contract.

## 8. Testing and quality gates

Canonical Python checks:

```bash
conda run -n geospatial pytest libs/geomemory/tests -q
conda run -n geospatial ruff check libs/geomemory/src
conda run -n geospatial mypy --strict libs/geomemory/src/geomemory
```

OpenSpec validation:

```bash
cd libs/geomemory
openspec validate --changes --strict
openspec validate --specs --strict
```

Web/gateway checks live in their respective project directories.

## 9. Known implementation drift and watch items

Because `openspec/specs/` is normative, the following drift should be tracked rather than hidden:

| Area | Spec direction | Current implementation | Action |
|---|---|---|---|
| Default vector backend | LanceDB default in `storage-architecture` | sqlite-vec is canonical lightweight path | Reconcile spec or code; document migration |
| Default text embedding | sentence-transformers default in `storage-architecture` | ONNX Xenova is canonical lightweight path | Reconcile spec or code |
| Docker targets | CLI + UI targets | Additional docs/rs/vector/vision/llamacpp targets | Usually acceptable superset; confirm release policy |
| Server/API | Library has no HTTP server | Gateway provides external HTTP routes | Keep library/gateway boundary explicit |
| Async jobs | Job table exists | Execution remains synchronous unless caller runs jobs | Implement worker or document limitation |
| DOCX | Dataset formats include `.docx` | `python-docx` is declared, but loader support needs verification in pipeline | Implement loader or remove format claim |

## 10. References

- Specs: [`../openspec/specs/`](../openspec/specs/)
- Current-state docs: [`current-state/`](current-state/)
- Architecture summary: [`architecture.md`](architecture.md)
- Components summary: [`components.md`](components.md)
- Data-flow summary: [`data-flow.md`](data-flow.md)
- Roadmap: [`roadmap.md`](roadmap.md)
- Gap analysis: [`gap-analysis.md`](gap-analysis.md)
