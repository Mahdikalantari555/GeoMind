# API Inventory — Current State

Snapshot: 2026-09-21 · `libs/geomemory` v0.1.0 alpha
Normative source of truth: [`../../openspec/specs/`](../../openspec/specs/)
Comprehensive summary: [`../library-capabilities.md`](../library-capabilities.md)

## 1. Public Python API (`import geomemory`)

Exports from `src/geomemory/__init__.py`: `__version__`, facade `GeoMemory`, 10 exceptions, and 22 domain models.

### Exceptions

`GeoMemoryError` ← `WorkspaceNotFoundError`, `CollectionNotFoundError`, `AssetNotFoundError`, `UnsupportedFormatError`, `DatabaseError`, `ModelNotLoadedError`, `NetworkDisabledError`, `EmbeddingUnavailableError`, `AbstentionError`.

### Facade `GeoMemory`

| Method | Behavior |
|---|---|
| `open` / `create` | Open or create a workspace |
| `settings` / `update_settings` | Read/update `workspace.yaml` |
| `create_collection` / `list_collections` / `get_collection` / `archive_collection` | Collection lifecycle |
| `ingest` | Full sync pipeline; dedups by SHA-256 |
| `search` | Hybrid RRF retrieval with filters |
| `ask` | Grounded QA with citations and abstention |
| `build_index` / `rebuild_index` | Embed segments → backend → manifest |
| `record_feedback` | Append feedback event |
| `get_review_queue` / `review_example` | Dataset review workflow |
| `export_dataset` | rag_eval/qa_eval/sft/preference export |
| `run_benchmark` | Eval runner entry |
| `list_assets` / `inspect` | Asset and revision inspection |
| `stats` | Workspace counters |
| `pipeline_stats` | Eight-field ingestion statistics |
| `traverse` | Entity/relation traversal |
| `image_index` / `search_images` | Optional vision index |

### Models

`Workspace`, `Collection`, `Asset`, `AssetRevision`, `Segment`, `EmbeddingRecord`, `Entity`, `CandidateMemory`, `KnowledgeChangeProposal`, `Job`, `RetrievalRun`, `Answer`, `Citation`, `SearchFilters`, `SearchHit`, `SearchResult`, `SpatialFilter`, `TemporalFilter`, `QAResult`.

### Stable sub-APIs

- `retrieval.search_service.SearchService`
- `qa.chat_service.ChatService`
- `ingest.pipeline.IngestionPipeline`
- `ingest.job_queue.JobQueue`
- `services.*` wrappers
- `rs.raster.spectral.ndvi/evi/compute_index`
- `storage.*`
- `feedback.candidate_memory.CandidateMemoryRepository`
- `services.entity_profile_service.EntityProfileService`
- `services.research_timeline_service.ResearchTimelineService`

## 2. CLI — `geomemory`

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

## 3. Gateway integration

The GeoFoundation gateway consumes GeoMemory server-side. Relevant additive routes from the temporal/entity specs are:

```http
GET /api/v1/memory/entities/{entity_name}
GET /api/v1/research/timeline?project=X&type=Y&as_of=Z&offset=0&limit=50
```

The library itself remains in-process; these are integration contracts, not a built-in GeoMemory HTTP server.

## 4. Dashboard

The Streamlit reference UI consumes only the public facade. It is optional and not part of the core library contract.

## 5. What does not exist

- No built-in GeoMemory HTTP/REST/gRPC/MCP server.
- No authentication/authorization layer.
- No background worker process for jobs.
- No plugin loading from external packages (registries are in-process only).