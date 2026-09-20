# Component Map — Current State

Snapshot: 2026-09-21 · `libs/geomemory` v0.1.0 alpha
Normative source of truth: [`../../openspec/specs/`](../../openspec/specs/)
Comprehensive summary: [`../library-capabilities.md`](../library-capabilities.md)

## `src/geomemory/` — 18 packages

### `core/` — models, facade, configuration, registries

| Unit | Responsibility |
|---|---|
| `models.py` | Pydantic v2 domain models, including workspace, assets, segments, raster/vector records, relations, conversations, QA, feedback, jobs, candidate memory, knowledge proposals, and search models |
| `workspace.py` | Public `GeoMemory` facade: open/create, collections, ingest, search, ask, indexing, feedback, evaluation, stats, traversal, candidate merging |
| `config.py` | `workspace.yaml` persistence and environment overrides |
| `events.py` | In-process domain event bus |
| `exceptions.py` | Public exception hierarchy |
| `hashing.py` | SHA-256 hashing and object-store path sharding |
| `plugin_registry.py` | Generic registry infrastructure for loaders/chunkers/embedders/backends |

### `ingest/`

| Unit | Responsibility |
|---|---|
| `loaders/` | Text, code, PDF, OpenDataLoader PDF, GeoJSON, GeoTIFF, Shapefile parsing |
| `chunkers/` | Fixed-size and header-preserving token chunking |
| `pipeline.py` | Loader resolution, parsing, chunking, spatial metadata, persistence |
| `job_queue.py` | DB-backed job state model |
| `vision_embed.py` | Vision embedding integration for image paths |

### `embeddings/`

| Unit | Responsibility |
|---|---|
| `provider.py` | ONNX, OpenAI, Voyage, and custom embedding providers |
| `onnx_text.py` | ONNX tokenizer/model inference, mean pooling, L2 normalization |
| `hub.py` | Local embedding model hub inventory and resolution |
| `factory.py` | Text/vision embedder selection from settings |
| `hashing_text.py` | Dependency-free n-gram hashing fallback |
| `llama_cpp_text.py`, `llama_cpp_vision.py` | Legacy GGUF embedding paths |
| `olmoearth_vision.py` | Native torch OLMoEarth vision embedder |
| `vision_downloader.py` | Opt-in vision model download/cache handling |
| `text_embedder.py`, `vision_embedder.py` | Embedder protocols and placeholder vision embedder |
| `normalization.py` | L2 normalization helpers |

### `index/`

| Unit | Responsibility |
|---|---|
| `sqlite_vec_backend.py` | Per-space `vec0` cosine virtual tables inside SQLite |
| `lance_backend.py` | Embedded LanceDB backend |
| `qdrant_backend.py` | Server-mode Qdrant backend |
| `vector_backend.py` | Persisted dense vector backend |
| `numpy_backend.py` | Pure-numpy fallback backend |
| `storage_backend.py` | Unified storage backend protocol |
| `backend.py` | Retrieval backend protocol |
| `image_backend.py`, `image_index.py` | Vision vector index and search |
| `manifest.py` | Index manifest read/write |

### `retrieval/`

| Unit | Responsibility |
|---|---|
| `query_parser.py` | Query cleaning, filter extraction, intent detection |
| `fusion.py` | RRF and linear rank fusion |
| `deduplicator.py` | Exact dedup and per-document diversity |
| `spatial_filter.py`, `temporal_filter.py` | Bbox and time-window post-filters |
| `search_service.py` | Canonical search orchestration and hit filtering |
| `context_packer.py` | Token-budgeted evidence packing for QA |

### `qa/`

| Unit | Responsibility |
|---|---|
| `chat_service.py` | Retrieve → pack → prompt → generate → cite → abstain → persist |
| `backend.py` | LLM backend protocol and null backend |
| `backend_factory.py` | LLM backend selection from settings |
| `llama_cpp_backend.py` | Local GGUF generation |
| `api_backend.py` | OpenAI-compatible API generation |
| `prompts.py` | Grounded QA, research, and code prompts |
| `citation.py` | Citation extraction, mapping, validation |
| `abstention.py` | Abstention detection and reason classification |

### `rs/`

| Unit | Responsibility |
|---|---|
| `raster/reader.py`, `metadata.py` | rasterio reads and scene metadata extraction |
| `raster/tiler.py` | Scene tiling with window metadata |
| `raster/preview.py` | PNG previews |
| `raster/spectral.py` | NDVI, EVI, band validation, generic index dispatch |
| `vector/reader.py` | GeoJSON/vector reading |
| `persist.py` | Scene/vector persistence and RTree entries |

### `feedback/`, `eval/`, `knowledge/`, `services/`, `storage/`, `cli/`

| Package | Responsibility |
|---|---|
| `feedback/` | Candidate memory repository/service, scoring, proposals, review queue, dedup, dataset exporters |
| `eval/` | Retrieval/QA metrics, benchmark runner, pipeline stats, run store, reporter |
| `knowledge/` | Entity/relation extraction helpers |
| `services/` | Thin orchestration wrappers, doctor, index/ingestion/search/chat/feedback/job services, entity profile and research timeline services |
| `storage/` | SQLite connect/migrate, object store, asset layout, repositories |
| `cli/` | Click command group with lazy command registration |

## Apps, containers, and eval assets

| Path | Role |
|---|---|
| `apps/dashboard/` | Current Streamlit reference UI |
| `apps/app.py` | Legacy/simple Streamlit entry point used by UI container |
| `Dockerfile` | Multi-target torch-free image build |
| `docker-compose.yml` | Qdrant + GeoMemory UI stack |
| `docker-compose.dev.yml` | Development bind-mount stack |
| `geomemory-evals/` | Datasets, scratch workspaces, and immutable run artifacts |

## Workspace directory layout

```text
workspace/
├── .geomemory
├── workspace.yaml
├── geomemory.db
├── objects/<aa>/<bb>/<sha256>
└── indexes/<space_id>/manifest.json
```
