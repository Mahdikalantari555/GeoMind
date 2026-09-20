# GeoMemory — Current State Documentation

Snapshot: 2026-09-21 · Package version `0.1.0` (alpha)
Normative source of truth: [`../openspec/specs/`](../openspec/specs/)
Comprehensive summary: [`../library-capabilities.md`](../library-capabilities.md)

These documents describe what exists today. They are descriptive, not normative. Requirements live in `openspec/specs/`; change proposals live in `openspec/changes/`.

| Document | Contents |
|---|---|
| [architecture.md](architecture.md) | System architecture, layers, runtime topology |
| [components.md](components.md) | Component map: modules, responsibilities, key classes |
| [data-flow.md](data-flow.md) | Ingestion, indexing, search, QA, feedback, temporal, and eval flows |
| [database-schema.md](database-schema.md) | SQLite schema, virtual tables, migrations, object-store layout |
| [api-inventory.md](api-inventory.md) | Public Python API + CLI command inventory |
| [dependency-graph.md](dependency-graph.md) | Internal module dependencies + external packages |
| [deployment.md](deployment.md) | Runtime/deployment architecture, Docker/compose |
| [tech-debt.md](tech-debt.md) | Current debt, drift, missing tests/docs |

## One-page summary

GeoMemory is a local-first Python library and CLI that turns heterogeneous research assets — documents, code, GeoTIFF scenes, GeoJSON layers, Shapefiles, PDFs — into a searchable spatiotemporal memory.

- **Facade**: everything goes through `geomemory.GeoMemory`.
- **Storage**: SQLite WAL + FTS5 + RTree + optional sqlite-vec virtual tables, plus a content-addressed object store.
- **Retrieval**: hybrid sparse + dense retrieval fused with RRF, followed by dedup/diversity and spatial/temporal/sensor filters.
- **Embeddings**: canonical lightweight path is ONNX `Xenova/all-MiniLM-L6-v2` with sqlite-vec; LanceDB, Qdrant, numpy, hashing, and legacy llama.cpp paths remain pluggable.
- **QA**: grounded generation through llama.cpp, OpenAI-compatible API, or abstaining null backend, with citation validation.
- **Feedback loop**: feedback events → dataset examples → review queue → exports (`rag_eval`, `qa_eval`, `sft`, `preference`).
- **Temporal/entity memory**: candidate beliefs carry `observed_at`, `superseded_by`, and `project`; services expose as-of reads, entity profiles, and research timelines.
- **Evaluation**: datasets, immutable run artifacts, pipeline stats, and run comparison under `geomemory-evals/`.
- **UI/containers**: optional Streamlit reference UI and Docker/compose assets.

Scale today: 18 library packages, 22 normative capability specs, Python ≥3.10, Pydantic v2, strict typing where enforced, and a torch-free base install.
