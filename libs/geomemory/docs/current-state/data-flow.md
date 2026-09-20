# Data Flow — Current State

Snapshot: 2026-09-21 · `libs/geomemory` v0.1.0 alpha
Normative source of truth: [`../../openspec/specs/`](../../openspec/specs/)
Comprehensive summary: [`../library-capabilities.md`](../library-capabilities.md)

## 1. Ingestion

`GeoMemory.ingest(source, collection_id, ...)`:

```text
source path/bytes
  → read raw bytes
  → SHA-256 content hash
  → duplicate revision short-circuit
  → detect MIME/kind
  → resolve loader
  → parse into drafts/segments
  → attach spatial metadata for raster/vector sources
  → store raw bytes in objects/<sha256>
  → insert asset + immutable asset_revision
  → insert segments; FTS5 triggers update segments_fts
  → persist raster_scene/tiles or vector_layer + RTree rows
  → update asset.current_revision_id
  → commit and return Job
```

PDF flow selects OpenDataLoader PDF when installed and Java is available; otherwise PyMuPDF. OpenDataLoader segments carry page and bbox locators for precise citations.

## 2. Index build

`GeoMemory.build_index(space_id)`:

```text
segments from SQLite
  → select text embedder from settings
  → embed pending segments in batches
  → insert embedding_record rows
  → upsert vectors into configured backend
  → save manifest with space_id, model_id, dimension, count
  → return build summary
```

Canonical lightweight backend: sqlite-vec `vec0` table per embedding space. Alternatives: LanceDB, Qdrant, persisted vector backend, and numpy fallback. Changing model or space requires rebuild; stale spaces are detected and warned about.

## 3. Search

`GeoMemory.search(...)`:

```text
query + filters
  → QueryParser clean/extract/detect intent
  → sparse FTS5 search
  → dense vector backend search
  → RRF or linear fusion
  → dedup + per-document diversity cap
  → spatial filter
  → temporal filter
  → sensor filter
  → collection scope
  → top_n SearchResult
  → persist RetrievalRun audit row
```

Candidate memories are searched separately and merged after authoritative hits. Superseded candidate rows are excluded unless `include_superseded=true`.

## 4. Grounded QA

`GeoMemory.ask(...)`:

```text
question
  → retrieve evidence
  → pack token-budgeted context
  → build mode prompt
  → generate via llama.cpp / OpenAI-compatible API / null backend
  → extract and map [n] citations
  → validate citations
  → detect abstention
  → persist conversation/turn/answer/citation
  → return QAResult
```

Missing API keys, offline API mode, HTTP failures, or insufficient evidence produce abstention with an explanatory reason rather than fabricated grounded content.

## 5. Feedback and dataset loop

```text
feedback event
  → dataset example builder
  → duplicate grouping
  → review queue pending/accepted/rejected
  → export accepted examples
  → rag_eval / qa_eval / sft / preference JSONL + dataset card
```

Candidate memories follow a separate governed lifecycle: proposed → supported → verified, with rejected preserved for audit and excluded from retrieval/ranking.

## 6. Temporal and entity flows

```text
candidate memory created with observed_at/project
  → optional supersession link to replacement row
  → as-of read walks supersession chain
  → effective observed_at = observed_at OR created_at
  → entity profile matches seeded aliases case-insensitively
  → current beliefs exclude superseded rows
  → history includes superseded rows
  → related entities come from relation joins and alias co-mention
  → research timeline filters by project/type/as_of and orders by observed_at DESC
```

## 7. Evaluation flows

```text
dataset under geomemory-evals/datasets/<name>/
  → ingest through production pipeline into scratch workspace
  → collect eight pipeline stats
  → run benchmark queries through production retrieval/QA
  → write immutable run artifacts
  → compare runs for stats/retrieval regressions
```

Run artifacts live under `geomemory-evals/runs/<dataset>/<timestamp>/` and are never mutated by later runs.

## 8. Cross-cutting flows

- **Provenance chain**: answer → citation → segment/locator → asset revision/hash → object-store bytes.
- **Candidate provenance**: candidate memory → provenance chain → feedback event.
- **Events**: `asset.created` is emitted as an extension point.
- **Jobs**: ingestion and service operations can be represented as `job` rows; execution remains caller-driven unless a worker is added.
