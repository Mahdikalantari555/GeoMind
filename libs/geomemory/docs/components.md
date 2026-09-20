# Components (summary)

Full detail: [`current-state/components.md`](current-state/components.md)
Comprehensive capability guide: [`library-capabilities.md`](library-capabilities.md)
Normative source of truth: [`../openspec/specs/`](../openspec/specs/)

| Package | Responsibility | Key units |
|---|---|---|
| `core/` | models, facade, config, events, hashing, registries | `GeoMemory` facade, 22+ Pydantic models, `EventBus`, `Registry[T]` |
| `ingest/` | parse & chunk sources into segments | loaders (text/code/pdf/geojson/geotiff/shapefile), chunkers (fixed_size/header_then_token), `IngestionPipeline`, DB-backed `JobQueue` |
| `embeddings/` | text/vision vector producers | ONNX `Xenova/all-MiniLM-L6-v2`, hashing fallback, legacy llama.cpp GGUF, OLMoEarth vision, hub, factory, provider |
| `index/` | vector storage & search | sqlite-vec, LanceDB, Qdrant, persisted `VectorBackend`, numpy fallback, `StorageBackend` protocol, `ImageIndex`, manifests |
| `retrieval/` | query understanding & result assembly | QueryParser, RRF fusion, dedup/diversity, spatial/temporal/sensor filters, context packer |
| `qa/` | grounded generation | ChatService, prompt modes, citation mapping/validation, abstention, llama.cpp and OpenAI-compatible API backends |
| `rs/` | remote-sensing domain | raster reader/tiler/preview/spectral (NDVI/EVI), vector reader, spatial persistence |
| `storage/` | persistence | SQLite connect/migrate, ObjectStore, repositories, schema.sql, migrations |
| `feedback/` | human signal → candidate memory → training data | candidate memory repo/service, scoring, proposals, review queue, 4 dataset exporters |
| `eval/` | quality measurement | recall/precision/MRR/nDCG, QA metrics, benchmark runner, pipeline stats, run store, reporter |
| `services/` | orchestration wrappers | index/ingestion/search/chat/feedback/job services, doctor, entity profile, research timeline |
| `cli/` | command surface | `geomemory` group, 11 commands, lazy imports |

Apps: `apps/dashboard/` (canonical UI), `apps/app.py` (legacy, used by UI container). Workspace on disk = `workspace.yaml` + `geomemory.db` + `objects/` + `indexes/`.