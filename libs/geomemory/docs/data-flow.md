# Data Flow (summary)

Full detail with diagrams: [`current-state/data-flow.md`](current-state/data-flow.md)
Comprehensive capability guide: [`library-capabilities.md`](library-capabilities.md)
Normative source of truth: [`../openspec/specs/`](../openspec/specs/)

Nine flows carry all data through GeoMemory:

1. **Ingest** (`GeoMemory.ingest`): bytes → SHA-256 → duplicate-hash short-circuit → MIME/kind detect → loader+chunker parse → blob to `objects/` → `asset`/`asset_revision` rows → `segment` rows (FTS5 triggers fire) → raster/vector spatial persistence (RTree) → commit → `asset.created` event → completed `Job`.
2. **Index build** (`build_index(space_id)`): segments from SQLite → embedder (ONNX/hashing/llama.cpp) → backend upsert (sqlite-vec/LanceDB/Qdrant/numpy) → JSON manifest.
3. **Search** (`GeoMemory.search`): QueryParser → parallel sparse (FTS5) + dense (vector backend) retrieval → RRF fusion → dedup + diversity cap → spatial/temporal/sensor filters → top_n `SearchResult` (+ persisted `RetrievalRun` audit row).
4. **Ask** (`GeoMemory.ask`): search for evidence → token-budgeted context pack → mode prompt (grounded_qa/research/code) → llama.cpp or OpenAI-compatible API generation → `[n]` citation extraction/mapping/validation → abstention check → persist conversation/turn/answer/citation → `QAResult`.
5. **Feedback loop**: feedback events → dataset example build + dedup → review queue (pending→accepted/rejected) → export as rag_eval / qa_eval / sft / preference with dataset card.
6. **Candidate memory lifecycle**: proposed → supported → verified; rejected preserved for audit and excluded from retrieval and ranking.
7. **Temporal/entity flow**: candidate memories carry `observed_at`, `superseded_by`, and `project`; as-of reads walk supersession chains; entity profiles match seeded aliases and join relation/co-mention data; research timelines filter by project/type/as_of and order by `observed_at` DESC.
8. **Evaluation flow**: dataset → ingest through production pipeline → collect eight pipeline stats → run benchmark queries → write immutable run artifacts → compare runs for regressions.
9. **Diagnostics flow** (`geomemory doctor`): environment, optional dependencies, database readability, LLM/Qdrant/PDF/vision/embedding state, and workspace integrity without mutating data.

Provenance thread through everything: `answer → citation → segment(locator) → asset_revision(hash) → objects/<sha256>`.