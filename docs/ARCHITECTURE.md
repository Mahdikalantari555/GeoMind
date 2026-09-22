# GeoFoundation — Architecture (Comprehensive)

> Status: Comprehensive architectural assessment, current state (post-MSc thesis phase).
> Normative sources: `CHARTER.md`, `STRUCTURE.md`, `SPEC_SERVER.md`, `SPEC_WEB.md`,
> each library's `AGENTS.md` and `openspec/specs/`, and the ADRs in
> `libs/geomemory/docs/adr/`.
>
> This document is the single architectural reference for GeoFoundation as a
> whole — not for any single library in isolation. It answers the questions a
> reviewer would ask about boundaries, dependencies, ownership, and risk.

## 0. How to read this document

- **Normative sources win.** If this document conflicts with a library's
  `openspec/specs/` or an ADR, the spec/ADR is authoritative. This document
  records the architectural assessment and identifies where the assessment
  diverges from the normative source.
- **Current state vs. intended state.** Sections 2–7 distinguish between what
  the architecture intends (per specs) and what the code actually does today.
- **Implementation bugs are excluded.** This document focuses on
  architectural invariants, responsibilities, and design decisions — not on
  bug reports or code quality.

## 1. Layer Model and Dependency Direction

The single architectural rule from `CHARTER.md`: **dependencies point strictly
downward.**

```
┌─────────────────────────────────────────────────────────────────────────┐
│ APPS        web SPA · CLI · (future) MCP server · notebooks             │
├─────────────────────────────────────────────────────────────────────────┤
│ GATEWAY     geofoundation/server — FastAPI · /api/v1                    │
│             composes all libs; apps consume ONLY this                   │
├─────────────────────────────────────────────────────────────────────────┤
│ APPLICATION libs/geoagent (SDK) · libs/data_engine (METRIC ETa)         │
│             agent framework · tools · playbooks · ET model              │
├─────────────────────────────────────────────────────────────────────────┤
│ LEARNING    libs/geolearn — online learning, incremental training       │
├─────────────────────────────────────────────────────────────────────────┤
│ MEMORY      libs/geomemory — knowledge store, hybrid search, citations  │
├─────────────────────────────────────────────────────────────────────────┤
│ MODELS      (future) GeoModels — model registry/zoo                     │
├─────────────────────────────────────────────────────────────────────────┤
│ STORAGE     SQLite (FTS5 · RTree · WAL) + content-addressed object      │
│             store (SHA-256)                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

**The rule:** Apps → Gateway → application/learning libs → memory → models →
storage. Apps never import libs directly; libs never import upward.

**What this means in practice:**

1. `apps/web` never imports `geomemory`/`geoagent`; it consumes only the
   gateway HTTP API (`SPEC_WEB.md`, AGENTS.md invariant 1).
2. `server/` imports only public facades (`geomemory.GeoMemory`, the geoagent
   SDK) — never library internals (`ARCHITECTURE.md`, AGENTS.md invariant 1).
3. `libs/geoagent` may depend on `libs/geomemory` (via the public facade only)
   and `libs/data_engine` (via the `[rs]` extra). It must not depend on
   `libs/geolearn` or anything above itself.
4. `libs/geolearn` may depend on `libs/geomemory` (to read candidate memories
   as training input). It must not depend on `libs/geoagent` or anything
   above itself.
5. `libs/data_engine` is a leaf algorithm library. It must not depend on any
   other library in the platform.

**The layer model is a contract, not a suggestion.** If a library needs to
cross the boundary, that is a feature request to the library it depends on —
not a reason to import internals.

## 2. Architectural Boundaries

Each library has explicit responsibilities and non-responsibilities. These are
architectural invariants, not implementation details.

### 2.1 GeoMemory — the knowledge engine

**What GeoMemory is:** A local-first, in-process Python library that turns
heterogeneous research assets (documents, code, GeoTIFF scenes, GeoJSON
layers) into a searchable, spatiotemporal, citation-grounded memory.
Version `0.1.0` alpha, Python ≥3.10, MIT. Everything runs on the user's
machine; offline by default; no telemetry.

**Explicit responsibilities:**

| Concern | Owned by GeoMemory |
|---|---|
| Workspace management | Create/open/close workspaces, settings, collections, doctor |
| Ingestion | Load files/bytes → immutable revisions, segments, spatial records |
| Text embedding | ONNX/GGUF/hashing embedders behind `TextEmbedder` protocol |
| Hybrid search | FTS5 sparse + dense vector fusion (RRF), filters, dedup |
| Grounded QA | Single retrieve→pack→generate→cite pass with abstention |
| Remote sensing | Raster/vector ingestion, spatial metadata, NDVI/EVI |
| Feedback | Append-only events, review queue, dataset exports |
| Candidate memory | Temporal belief layer, lifecycle states, supersession |
| Entity profiles | Alias-based entity views over candidate memories |
| Research timelines | Project-scoped chronological candidate memory views |
| Evaluation | Benchmarks, metrics, run storage/comparison |
| Provenance | SHA-256 content identity, citation chain, immutable revisions |

**What GeoMemory must never do:**

1. **Never run an agent loop.** No tool-calling, no multi-step planning, no
   LLM-driven reasoning loop. Grounded QA is a single retrieve→pack→generate
   pass, not an agentic loop. The `geoagent` `memory-tools` spec explicitly
   states: *"there is NO `geo_ask` tool in v0.x. Grounded generation is the
   agent's job."*
2. **Never host an HTTP/MCP server.** It is import-only. The roadmap defers
   the FastAPI/MCP server layer to v0.3.
3. **Never train or update models.** Embeddings and LLMs are loaded
   read-only; there is no `partial_fit`, no gradient step, no model
   versioning. That is GeoLearn's layer.
4. **Never write to its own DB from outside the facade.** All consumers must
   go through `geomemory.GeoMemory`. The `geomemorytest/` black-box suite
   enforces this for the whole monorepo.
5. **Never mix embedding spaces across modalities.** text.* vs vision ids —
   invariant 1 of the AGENTS.md.
6. **Never fabricate.** Abstention is a first-class outcome
   (`AbstentionError`, `NullBackend`), not a failure mode.

### 2.2 GeoAgent — the reasoning layer

**What GeoAgent is:** A lightweight, tool-calling agent framework for
remote-sensing workflows, built on top of the GeoMemory public API — not a
fork of it. Version `0.1.0` spec-phase.

**Explicit responsibilities:**

| Concern | Owned by GeoAgent |
|---|---|
| Agent harness | Own thin harness (~loop + registry + sessions); direct OpenAI-compatible calls |
| Tool registry | Typed tools with JSON-Schema params, manifest for prompts, validation |
| Agent core | Plan→tool-call loop with budgets, citations, abstention |
| Session state | Conversations, turns, tool-run references in `agent.db` |
| Memory tools | Thin wrappers over GeoMemory public facade (`geo_ingest`, `geo_search`, etc.) |
| GIS tools | Native rasterio/geopandas wrappers (reclassify, polygonize, symbology, zonal stats) |
| Advisor tools | Farm report + irrigation/fertilization/spraying recommendations |
| Playbooks | Saved, versioned tool sequences for deterministic fast-path replay |
| Citation contract | `[S#]` keys mapped to `geo_search` hits; invalid keys stripped |
| Tool audit | Every tool call persisted as `ToolRun` (status, latency, artifacts, error) |

**What GeoAgent must never do:**

1. **Never write GeoMemory's DB directly.** *"GeoAgent is a consumer: it
   imports nothing deeper than `import geomemory` root exports and never
   opens GeoMemory's SQLite directly."* All state flows through facade calls.
2. **Never own knowledge storage.** Agent-own state lives in a separate
   `agent.db` inside its workspace dir, distinct from `geomemory.db`.
3. **Never do local LLM runtimes in v0.x.** The `LLMBackend` protocol seam is
   reserved but no GGUF/llama.cpp implementation ships.
4. **Never train ML models.** The `learning-loop` spec is *"plumbing-only"*;
   active learning/incremental training is explicitly deferred. *"Core SHALL
   NOT import any ML module."*
5. **Never fabricate citations.** Invalid `[S#]` keys are stripped and
   recorded in answer metadata.
6. **Never bypass the registry.** Every tool call goes through
   `Registry.call()` → validation → audit `ToolRun` row. No execution without
   an audit row.
7. **Never do dynamic tool creation by the LLM.** Tools are statically
   registered.

### 2.3 GeoLearn — the adaptation layer

**What GeoLearn is:** An online learning framework for remote sensing
foundation model adapters. Version `0.1.0`, built on numpy and scikit-learn
for v1. It consumes frozen OLMoEarth embeddings and produces per-class
predictions via online classifiers with `partial_fit()`.

**Explicit responsibilities:**

| Concern | Owned by GeoLearn |
|---|---|
| Embedding cache | Persistent cache of frozen embeddings by `asset_id` in `geolearn.db` |
| Online classifiers | `SGDClassifier` per `(crop_type, region)` key with `partial_fit()` |
| Confidence model | Abstention on low confidence (default threshold 0.6) |
| Per-key classifier store | `ClassifierStore` managing one classifier per key |
| Frozen adapter | NN fallback over frozen OLMoEarth embeddings when <30 samples |
| Feedback training | `TrainingPipeline` reading accepted candidate memories |
| Model versioning | Versioned classifier saves (last 10) with rollback |
| Edge export | JSON+numpy export format runnable without sklearn at runtime |
| Personalization | User/region profiles with preferred classifier selection |
| Drift detection | (v2) River-style PageHinkley or simple error-rate detector |

**What GeoLearn must never do:**

1. **Never use PyTorch in v1.** Zero torch deps; numpy + scikit-learn +
   sqlite3 + joblib only. River is an optional `[river]` extra, lazily
   imported.
2. **Never do retrieval or ranking.** It consumes *frozen* OLMoEarth
   embeddings produced elsewhere; it does not embed, index, or search.
3. **Never write to GeoMemory.** It is a read-only consumer of
   `candidate_memory`. (See the caveat in Section 3.4 — it currently reads
   via raw SQLite, a documented controlled coupling.)
4. **Never host an agent loop.** It exposes `predict()` / `partial_fit()`;
   the agent calls it via tools.
5. **Never do concept drift detection or replay buffers in v1** — explicitly
   non-goals.

### 2.4 Data Engine — the physics layer

**What Data Engine is:** A remote-sensing data engine for Landsat and
Sentinel. It implements the METRIC ETa pipeline (energy-balance evapotranspiration)
and related geospatial analytics. Version `0.1.0`.

**Explicit responsibilities:**

| Concern | Owned by Data Engine |
|---|---|
| Landsat domain | Full METRIC ETa pipeline (`data_engine.landsat`) |
| Sentinel domain | Sentinel-2 processing (`data_engine.sentinel`) |
| Shared physics | `core`, `io`, `utils`, `surface`, `radiation`, `energy_balance`, `et`, `preprocess`, `output`, `validation`, `calibration`, `weather`, `settings` |
| DataCube | In-memory band/container operations |
| METRICPipeline | Landsat-specific pipeline orchestration |
| SentinelPipeline | Sentinel-specific pipeline orchestration |
| CLI | `data-engine` command line interface |

**What Data Engine must never do:**

1. **Never couple Landsat ↔ Sentinel domains.** *"Neither domain SHALL
   import from the other's sub-package."* Both may import shared top-level
   modules.
2. **Never be an agent, memory, or learning system.** It is pure scientific
   computation: radiation balance, energy balance, anchor-pixel calibration,
   ET extrapolation.
3. **Never mutate shared state.** It is a stateless pipeline:
   `METRICPipeline.run(landsat_dir, meteo_data, output_dir)` → GeoTIFFs + stats.
4. **Never hardcode model paths.** `SENTINEL_ROOT` is env-overridable.

### 2.5 Gateway and Apps (context)

The gateway (`server/`) is the platform's face. It composes all libs through
public facades only, serializes writes behind one `asyncio.Lock`, and serves
one active workspace at a time. Apps (`apps/web`) consume only the gateway
HTTP API — no direct library imports.

## 3. Dependency Graph

### 3.1 Intended dependency direction (per CHARTER)

```
apps/web, CLI, (future) MCP
        ↓
server/ (FastAPI gateway)
        ↓
libs/geoagent  ←─── libs/data_engine (metric_et)   [APPLICATION layer]
        ↓
libs/geolearn                                          [LEARNING layer]
        ↓
libs/geomemory                                         [MEMORY layer]
        ↓
(GGUF/ONNX models, OLMoEarth)                          [MODELS layer]
        ↓
SQLite + content-addressed object store                [STORAGE layer]
```

**Permitted dependencies:**

| Consumer | May depend on | Evidence |
|---|---|---|
| `geoagent` | `geomemory` (public facade only) | `memory-tools` spec; `geoagent/tools/memory_tools.py:36` uses `geomemory.GeoMemory.open` |
| `geoagent` | `data_engine` (via `[rs]` extra) | `geoagent-rs-tool` spec: `[rs]` = `["geolearn", "data-engine"]`; `rs_compute_et` wraps `data_engine.landsat.METRICPipeline` |
| `geoagent` | `geolearn` (lazy, via tools) | `geolearn_tools.py:12` `from geolearn.training_pipeline import TrainingPipeline` |
| `geolearn` | `geomemory` (candidate_memory) | `training_pipeline.py:49` reads `geomemory.db` |
| `server` | `geomemory`, `geoagent` | `ARCHITECTURE.md`: *"imports ONLY public facades"* |
| `apps/web` | server only | AGENTS.md invariant 1: *"apps/web never imports geomemory/geoagent"* |

### 3.2 Actual dependency direction (current code)

```
apps/web ──HTTP──▶ server/ ──imports──▶ geomemory (facade) + geoagent (facade)
                                      └──▶ geolearn (tools, lazy)
geoagent/ ──imports──▶ geomemory (facade) + data_engine (tools, lazy) + geolearn (tools, lazy)
geolearn/ ──imports──▶ numpy, scikit-learn, sqlite3, joblib + geomemory.db (raw)
data_engine/ ──imports──▶ numpy, rasterio, geopandas, matplotlib (internal only)
```

### 3.3 Forbidden dependencies (enforced by spec, not by tooling)

- **`geomemory` → `geoagent`**: forbidden. GeoMemory has no knowledge of
  agents. Its roadmap v0.3 *"agent interface"* is an outbound HTTP/MCP
  *server it exposes*, not an inbound dependency.
- **`geomemory` → `geolearn`**: forbidden. The feedback→training arrow is
  one-way: GeoMemory exports datasets; GeoLearn consumes them.
- **`geomemory` → `data_engine`**: forbidden. GeoMemory's `rs/` module has
  its *own* pure-numpy NDVI/EVI (`geomemory.rs.raster.spectral`); it does not
  import `data_engine`.
- **`data_engine` → `geoagent`/`geolearn`/`geomemory`**: forbidden. It is a
  leaf algorithm library.
- **`geolearn` → `geoagent`**: forbidden. GeoLearn is invoked *by* the agent,
  not the reverse.

### 3.4 Known violations / risks (deviations from the intended graph)

1. **`geoagent` → `geolearn` is upward.** CHARTER puts LEARNING *above*
   APPLICATION, but `geoagent/tools/geolearn_tools.py` imports `geolearn`.
   The chain is `geoagent → geolearn → geomemory`, which inverts the
   intended `geoagent → geomemory` direct edge.
2. **`geolearn` reads `geomemory` via raw SQLite, not the facade.**
   `training_pipeline.py:49-91` opens `geomemory.db` directly and runs
   `SELECT ... FROM candidate_memory`. The spec calls this *"a documented
   controlled coupling (not a full facade dependency)"*, but it breaks the
   facade-only invariant that geoagent and the dashboard respect.
3. **`[rs]` extra bundles `["geolearn", "data-engine"]` in geoagent.**
   This is intentional (both are remote-sensing processing capabilities) but
   couples their release cycles and creates a soft dependency on GeoLearn
   from GeoAgent.

## 4. Monolith Risk Assessment

### 4.1 Existing safeguards

1. **Facade-only consumption is a normative invariant, enforced by a
   black-box test suite.** `libs/geomemory/geomemorytest/` tests only the
   public surface. `ARCHITECTURE.md` inherited invariant #4: *"Facade-only
   consumption: gateway/apps import `geomemory` public API, never internals."*
2. **GeoAgent's memory tools have a hard-coded import guard.**
   `memory_tools.py:21-38` does `importlib.import_module("geomemory")` and
   uses only `geomemory.GeoMemory.open`. The module docstring reads:
   *"Invariant: `import geomemory` root exports exclusively; never
   GeoMemory's DB."*
3. **Separate DBs per concern.** `geomemory.db`, `agent.db`, and
   `geolearn.db` are three distinct SQLite files. A writer in one cannot
   corrupt another's tables.
4. **Protocol-based extensibility as the sanctioned extension seam.**
   `TextEmbedder`, `VisionEmbedder`, `RetrievalBackend`, `LLMBackend`,
   `LoaderRegistry`, `ChunkerRegistry` — *"Add impls, don't fork callers."*
5. **Gateway serialization.** `state.py` holds one `asyncio.Lock`
   (`write_lock`) serializing all writes; one uvicorn worker; one active
   workspace.
6. **Artifact identity = SHA-256.** Tool outputs are registered as
   `ArtifactRef(path, sha256)`. Cross-library references are
   content-addressed rather than pointer-addressed.
7. **OpenSpec change workflow.** Each lib has `openspec/changes/` with
   proposal → spec → tasks → archive. Feature work must be proposed before
   implemented.

### 4.2 Planned safeguards

1. **GeoMemory v1.0 "Stability contract":** SemVer + deprecation policy;
   *"public API frozen to documented surface; `py.typed` verified in
   release."*
2. **GeoMemory v0.1 consolidation:** *"Extract inline SQL from facade into
   repositories; split facade into composition of services"* — attacking the
   1152-LOC god-object (`core/workspace.py`).
3. **GeoMemory v0.1 #1:** *"route facade FTS/dense retrieval through
   `SearchService` as `RetrievalBackend` adapters"* — removing the duplicated
   `_rrf_fuse`/`_hit_sensor` convergence debt.
4. **GeoMemory v0.3:** MCP server exposing search/ask — a sanctioned,
   contract-first agent interface rather than ad-hoc imports.
5. **CI gates (planned, not yet enforced):** ruff + mypy `--strict` + pytest
   + coverage ≥80. Currently *"configured, not yet CI-enforced"*.
6. **GeoLearn's own design:** separate `geolearn.db`, per-key classifiers in
   `classifier_state`, versioned saves (last 10) with rollback — isolating
   learning state from memory state.

### 4.3 Unprotected areas / gaps

- **No import-time or CI enforcement of the downward-dependency rule.** The
  CHARTER rule is prose in a markdown file. Nothing fails the build if
  `geomemory` imports `geoagent`.
- **GeoLearn's direct-SQL coupling to `geomemory` is a live precedent.** If
  it is acceptable for GeoLearn, the door is open for others. The spec calls
  it "documented" but there is no architectural review gate.
- **Shared utility modules are not yet a coupling point** — each lib has its
  own `utils/` — but `data_engine` shares `core`, `surface`, `radiation`
  across its two domains, which is a *within-lib* coupling that could leak.
- **The `[rs]` extra in geoagent now bundles `["geolearn", "data-engine"]`**
  (`geoagent-rs-tool` spec). This creates a soft coupling: geoagent's
  optional-dependency graph drags both learning and data-engine in together.

## 5. Public Contracts

### 5.1 GeoMemory

- **Public API:** `src/geomemory/__init__.py` — the `GeoMemory` facade + 17
  Pydantic models (`Asset`, `Segment`, `CandidateMemory`, `Citation`,
  `SearchHit`, `QAResult`, `FeedbackEvent`, `Entity`, `RetrievalRun`,
  `KnowledgeChangeProposal`, `Job`, `EmbeddingRecord`, `Turn`, `Workspace`,
  `WorkspaceConfig`, `Collection`, `AssetRevision`, `SearchFilters`,
  `SearchResult`, `SpatialFilter`, `TemporalFilter`, `Answer`) + 8
  exceptions rooted at `GeoMemoryError` + `EmbeddingModelHub` + 4
  `doctor_*` functions.
- **Internal:** everything under `core/`, `ingest/`, `embeddings/`, `index/`,
  `retrieval/`, `qa/`, `rs/`, `storage/`, `feedback/`, `eval/`, `knowledge/`,
  `services/`, `cli/`. The `storage/repositories/*` raw SQL, `schema.sql`,
  migrations, and `core/workspace.py` internals are all internal.
- **Breaking changes:** Currently **alpha (0.1.0) with no formal policy**.
  The v1.0 roadmap promises *"SemVer + deprecation policy; public API frozen
  to documented surface."* Today, anything goes. The black-box
  `geomemorytest/` suite is the only backstop.
- **Can another team build against the public interface alone?** Yes — the
  Streamlit dashboard does exactly this, and `geomemorytest/` exists
  specifically to prove it. The gateway does too. The contract is:
  `GeoMemory.open(path)` → facade methods → Pydantic models. No DB access
  needed.

### 5.2 GeoAgent

- **Public API:** `src/geoagent/__init__.py` — extremely thin:
  `AgentSettings`, `ArtifactRef`, `Registry`, `RunContext`, `ToolDefinition`,
  `ToolResult`, `load_settings`, `__version__`. That is the entire surface.
- **Internal:** `agent.py` (AgentCore), `store.py`, `config.py`, `llm/*`,
  `plugins.py`, `playbooks.py`, `tools/*`.
- **Breaking changes:** No formal policy; 0.1.0 spec-phase. The tool registry
  is the stability boundary — tool *names* and JSON-Schema params are the
  contract the LLM and UI depend on.
- **Can another team build against it?** Yes, via the registry contract. A
  consumer needs only `Registry`, `ToolDefinition`, `ToolResult`,
  `RunContext`. The gateway's `AgentService` (`services/agent.py`)
  demonstrates this — it constructs the registry and core without touching
  internals. The MCP server spec (P5) is designed to expose exactly this
  surface.

### 5.3 GeoLearn

- **Public API:** `src/geolearn/__init__.py` — ~22 names: `EmbeddingCache`,
  `OnlineClassifier`, `ClassifierStore`, `ConfidenceModel`, `PredictionResult`,
  `ProfileStore`, `UserProfile`, `UserSettings`, `UserSettingsStore`,
  `ModelVersion`, `ModelVersionManager`, `EdgeLoader`, `CalibrationCurve`,
  `ClassifierChoice`, region helpers, exceptions.
- **Internal:** `streaming.py`, `drift.py`, `scheduler.py`, `association.py`,
  `adapter.py`, `frozen_adapter.py`, `calibration.py`, `edge.py`,
  `versioning.py`, `cache.py`, `persistence.py`, `training_pipeline.py`.
- **Breaking changes:** 0.1.0, no policy. The `PredictionResult` dataclass
  and the `(crop_type, region)` keying scheme are the contracts.
- **Can another team build against it?** Yes — `geoagent/tools/geolearn_tools.py`
  does exactly this, importing only `geolearn.training_pipeline.TrainingPipeline`,
  `geolearn.persistence.ClassifierStore`, `geolearn.user_settings.UserSettingsStore`,
  `geolearn.versioning.ModelVersionManager`. Note: these are *submodule*
  imports, not the top-level `__init__` — a slightly weaker guarantee.

### 5.4 Data Engine

- **Public API:** `src/data_engine/__init__.py` — `DataCube`, `METRICPipeline`,
  `SentinelPipeline`, `LandsatReader`, `MeteoReader`, the radiation/surface/
  energy-balance classes, `constants`, `SENTINEL_ROOT`, plus the shared
  submodules (`core`, `io`, `surface`, `radiation`, `energy_balance`, `et`,
  `preprocess`, `output`, `validation`, `calibration`, `weather`, `settings`,
  `utils`).
- **Internal:** `landsat/*`, `sentinel/*` domain sub-packages; `cli/`;
  `config/`.
- **Breaking changes:** 0.1.0, no policy. The `DataCube` round-trip contract
  and `METRICPipeline.run()` signature are the stability boundaries.
- **Can another team build against it?** Yes — the `rs_compute_et` geoagent
  tool wraps `data_engine.landsat.METRICPipeline` and nothing else.

## 6. Knowledge Ownership

| Concept | Authoritative owner | Rationale |
|---|---|---|
| **Documents** (raw bytes, parsers) | GeoMemory (`ingest/`, `rs/`) | Content identity = SHA-256; revisions immutable; loaders are registered in GeoMemory |
| **Segments** (chunked text/units) | GeoMemory (`ingest/chunkers`, `storage/repositories/segment`) | Segments are the unit of citation; FTS5 `segments_fts` lives in `geomemory.db` |
| **Embeddings** (vectors, spaces) | GeoMemory (`embeddings/`, `index/`) | Space isolation invariant; manifests record model/dim/checksum; `EmbeddingRecord` rows |
| **Candidate memories** | GeoMemory (`feedback/candidate_memory.py`, `candidate_memory` table) | Temporal fields (`observed_at`, `superseded_by`), lifecycle states, supersession chains — all GeoMemory specs |
| **Entity profiles** | GeoMemory (`services/entity_profile.py`, `entity-profiles` spec) | Alias-based entity views over candidate memories; `GET /api/v1/memory/entities/{name}` |
| **Relations** | GeoMemory (`relation` table, `entity` table) | Graph edges between entities; consumed by entity profiles |
| **Feedback events** | GeoMemory (`feedback/`, `feedback_event` table) | Append-only raw events; dedup; review queue; 4 export types |
| **Evaluation datasets** | GeoMemory (`eval/`, `eval-datasets` spec) | `geomemory-evals/datasets/<name>/queries.yaml`; benchmark runner; run storage/comparison |
| **Research timelines** | GeoMemory (`services/research_timeline.py`, `research-timelines` spec) | `GET /api/v1/research/timeline`; paginated, `observed_at`-descending candidate views |
| **Learned models** (classifiers, versions) | **GeoLearn** (`ClassifierStore`, `ModelVersionManager`) | Per-key SGDClassifier joblib files; versioned saves with rollback; `geolearn.db` |
| **Agent memories** (conversations, turns) | **GeoAgent** (`store.py`, `agent.db`) | *"Conversations SHALL persist in `agent.db` (separate from GeoMemory's DB)"* (`agent-core` spec) |
| **Task plans** | **GeoAgent** (`agent.py` planning step) | Emitted before execution, visible in transcript; not persisted as a separate artifact |
| **Tool execution history** | **GeoAgent** (`registry.py` ToolRun audit rows) | tool name, args hash, status, latency, artifacts, error — in `agent.db` |
| **Raster scenes** (metadata) | GeoMemory (`rs/raster`, `raster_scene`/`raster_tile` tables) | Ingested scene metadata (sensor/bbox/date) drives spatial/temporal filters |
| **Spectral indices** (NDVI/EVI) | **GeoMemory** (`rs/raster/spectral.py`, pure-numpy) for NDVI/EVI; **GeoAgent** (`gis_tools.py`) for NDWI/SAVI/reclassify/polygonize | GeoMemory owns the two shipped indices; GeoAgent owns the *tool wrappers* and the broader set |
| **ET outputs** (ET_daily.tif, ETrF, LE, H, Rn, G, dT) | **Data Engine** (`data_engine.landsat.METRICPipeline`) | Full energy-balance pipeline; exposed to the agent via `rs_compute_et` |

**Boundary note:** spectral indices have a split ownership that is a known
gap. GeoMemory ships NDVI/EVI as pure-numpy functions; NDWI/SAVI live in
GeoAgent's `gis_tools.py` as *"local pure-numpy formulas (GeoMemory
implements only NDVI/EVI today — gap documented upstream)."* This is a
duplication risk: the same formula could exist in two libraries.

## 7. Reasoning Ownership

| Capability | Owner | Rationale |
|---|---|---|
| **Retrieval** | GeoMemory (`retrieval/`, `SearchService`) | RRF fusion, sparse/dense backends, spatial→temporal→sensor filters, dedup, diversity caps. Canonical single path: `rrf_fuse` + `apply_hit_filters`. |
| **Ranking** | GeoMemory | Part of retrieval; RRF is the ranking algorithm. No learned reranker (explicitly out of scope, `roadmap.md`). |
| **Hypothesis generation** | **GeoAgent** | The LLM proposes a plan (`agent.py:22` — *"first emit a short numbered plan"*), then executes via tools. GeoMemory has no LLM-driven hypothesis capability. |
| **Causal inference** | **Not yet owned.** Would live in GeoAgent (LLM reasoning over retrieved evidence) or a future case-study layer. No library implements it. |
| **Temporal reasoning** | **GeoMemory** (`temporal-memory` spec, `candidate_memory.observed_at`) | As-of queries, supersession chains, point-in-time belief reconstruction. This is *data* reasoning, not LLM reasoning. |
| **Multi-step planning** | **GeoAgent** (`agent-core` spec: *"first emit a short step plan, then execute stepwise"*) | Playbooks are the deterministic fast-path; the LLM loop is the general path. |
| **Tool selection** | **GeoAgent** (`registry.py`, manifest in system prompt) | The LLM selects from a token-budget-capped manifest; least-recently-used families collapse on overflow. |
| **Self-reflection** | **GeoAgent** (implicit) | Budget exhaustion produces a partial-results summary with skipped steps; invalid citations are stripped and recorded. No explicit self-critique loop yet. |
| **Memory consolidation** | **GeoMemory** (`evolutionary-memory` spec) | Candidate memory lifecycle: proposed → supported → verified → rejected; supersession; audit trails. This is *governed memory evolution*, distinct from learning. |
| **Feedback learning** | **GeoLearn** (`TrainingPipeline`, `partial_fit`) | Converts accepted candidate memories into classifier weight updates. GeoMemory owns the *raw feedback*; GeoLearn owns the *weight update*. |
| **Knowledge revision** | **GeoMemory** (`candidate_memory.superseded_by`, `KnowledgeChangeProposal`) | Reversible, auditable. *"Exclude superseded candidates from search by default; include them only on explicit opt-in."* |

**The cleanest way to see the split:** GeoMemory owns *what is known and
when* (retrieval, ranking, temporal belief, consolidation, revision).
GeoAgent owns *how to think with it* (planning, tool selection, hypothesis,
abstention). GeoLearn owns *how the system gets better* (weight updates from
feedback). No capability is duplicated across these boundaries in the specs
— but the GeoLearn direct-SQL read of `candidate_memory` (Section 3.4) means
the *input* to feedback learning bypasses the owner's facade.

## 8. GeoMemory Evaluation

Per the `gap-analysis.md` and `roadmap.md`:

- **Infrastructure-complete**: **Mostly, with caveats.** SQLite + FTS5 +
  RTree + content-addressed object store + WAL + migrations are in place.
  The job table exists but is **not consumed asynchronously** — ingestion is
  synchronous. No background worker. No ANN (brute-force numpy only;
  degrades linearly beyond ~50k segments). No blob GC.
- **Feature-complete**: **No.** Missing: vision pipeline is experimental
  (`PlaceholderVisionEmbedder`), no DOCX loader despite `python-docx` being
  declared, no multilingual query parsing (English-only), no model download/
  verification helper, no agent/MCP interface (import-only), no async job
  execution.
- **Research-complete**: **No.** The core research hypothesis (RAG + feedback
  loop for stress classification) is not yet validated end-to-end. The
  feedback→training→better-answers loop is *plumbing* in GeoAgent
  (`learning-loop` spec: *"plumbing-only"*) and *architected but unbuilt* in
  GeoLearn.
- **Production-ready**: **No — alpha (0.1.0).** No CI enforcing quality gates,
  no SemVer policy, facade is a 1152-LOC god-object, no deprecation story.

**Largest remaining architectural gaps** (excluding implementation bugs):

1. **The async job story is half-built.** A `job` table with states exists;
   nothing consumes it. Long ingests block the caller. This is a
   scalability wall for the platform's signature loop (ingest → index →
   search).
2. **No agent surface.** The library is import-only. roadmap v0.3 defers the
   FastAPI/MCP server. Until then, every agent integration (including
   GeoAgent itself) must import Python — the gateway is the only HTTP surface
   and it is a separate project.
3. **Retrieval scalability.** Brute-force dense search, no ANN.
   `RetrievalRun` JSON blobs grow unbounded. Object store has no GC. This is
   a known scaling risk, not a hidden one.
4. **The facade god-object.** `core/workspace.py` at 1152 LOC mixes
   orchestration and inline SQL. v0.1 plans to extract repositories and route
   through `SearchService`, but this is not yet done.
5. **Multilingual is declared but not implemented.** `--language fa` is
   stored; query parser, abstention heuristics, and prompts are
   English-only. Persian is a thesis requirement (`SPEC_WEB.md`: *"thesis
   requires Persian demo"*).
6. **Vision is a stub.** `PlaceholderVisionEmbedder` is not wired into the
   default pipeline. The OLMoEarth GGUF path exists but is experimental and
   not integrated into ingest→tile→embed→search end-to-end.
7. **Storage/embedding drift.** The `storage-architecture` spec names LanceDB
   + sentence-transformers as defaults; the code uses sqlite-vec + ONNX
   Xenova. This drift is documented but unresolved — it means the normative
   spec and the implementation disagree on the canonical path.

## 9. GeoAgent Evaluation

**Long-term vision:** GeoAgent is intended to become a **domain-specific
scientific reasoning assistant** — not a general-purpose agent framework, not
an LLM wrapper.

Evidence from `project.md`:

- *"A lightweight, tool-calling agent framework for remote-sensing workflows"*
- The persona table: **Supervisor** (advisor), **GIS/RS researcher** (natural-
  language → pipeline execution), **Developer** (add tools without touching
  the harness).
- The thesis framing: GeoAgent is *"the engineering product that makes those
  axes operable through an agent"* — stress detection, stress discrimination,
  plant health from imagery.

It is **not** intended to become:

- A generic agent framework (decision #1: *"Own thin harness... nanobot/
  Hermes/fx are design references, never dependencies"*).
- An ML training system (decision #5: *"Agent project first — Active Learning
  / incremental-model placement deferred"*).
- A local-LLM runtime (decision #2: *"Local LLM support is out of scope for
  the first versions"*).
- A multi-agent orchestrator (`agent-core` non-goals).

**Capabilities intentionally excluded** (from specs' non-goals):

- Local LLM runtimes (v0.x)
- Fine-tuning the LLM
- Multi-agent orchestration
- Uncertainty sampling, replay buffer, incremental XGBoost, scenario runner
  (A/B/C), forgetting-rate computation (`learning-loop` non-goals)
- Subprocess isolation per tool, remote tool execution, dynamic tool creation
  by the LLM (`tool-registry` non-goals)
- Cross-workflow DAG engine, conditional branching beyond param templates
  (`playbooks` non-goals)
- Reprojection/resampling tools, web map tiles, interactive maps, GEE script
  execution (`gis-tools` non-goals)
- Multi-tenant web deployment, notification/scheduling, sensor/IoT ingestion,
  automatic prescription without human confirmation (`advisor` non-goals)
- Multimodal/vision QA (`memory-tools` non-goals)

The design is deliberately narrow: **retrieve → tool → cite → abstain**, with
playbooks as the deterministic fast path. The `[S#]` citation contract and
the budget guardrails (max 8 tool calls, 120s wall clock, 6 LLM iterations)
are the core safety mechanisms.

## 10. GeoLearn Evaluation

GeoLearn's unique responsibility is **converting frozen embeddings + sparse
human feedback into continuously-updated per-region classifier weights, with
calibrated confidence and abstention.** It is the only library that does
*learning*.

What it is **not**:

| Comparison | Distinction |
|---|---|
| **vs. GeoMemory candidate memories** | Candidate memories are *symbolic beliefs* with lifecycle states (proposed/supported/verified/rejected) and temporal fields. GeoLearn's classifiers are *numeric weights* over embedding vectors. GeoMemory owns the belief store; GeoLearn owns the weight update. The `TrainingPipeline` reads candidate memories but only those in `verified`/`supported` states — it does not manage the lifecycle. |
| **vs. evaluation datasets** | Eval datasets (`geomemory-evals/`) are *static benchmark fixtures* with `queries.yaml` for measuring retrieval/QA quality. They are inputs to `geomemory eval run`, not training data. GeoLearn's training signal comes from *accepted feedback*, not benchmark queries. |
| **vs. traditional ML pipelines** | Traditional pipelines do a single `fit()` on a static dataset, then deploy. GeoLearn does `partial_fit()` in batches keyed by `(crop_type, region)`, with versioned saves (last 10), rollback, and a NN fallback when <30 samples. It is designed for *data scarcity and continual adaptation*, the thesis's core hypothesis. |
| **vs. RL-style feedback loops** | RL would update a policy from reward signals. GeoLearn updates classifier weights from *labeled corrections* (accepted/rejected candidate memories). It is supervised online learning, not reinforcement learning. There is no reward model, no policy gradient, no environment. The `OnlineScheduler` batches by count *or* time — a simple trigger, not an RL-style credit assignment. |

**What uniquely differentiates GeoLearn** (from `core-framework` proposal):

1. **Per-key isolation:** one SGDClassifier per `(crop_type, region)`,
   defaulting to `("unknown", "global")`. Sub-region keys inherit parent
   weights (`region-specific-adaptation` spec).
2. **Cold-start bridge:** `FrozenEmbeddingAdapter` does NN voting over frozen
   OLMoEarth embeddings when the classifier has <30 samples, then hands off
   automatically.
3. **Abstention as a first-class output:** `PredictionResult.abstain` is set
   when max-proba < threshold (default 0.6), with isotonic calibration (v0.2)
   and entropy-based uncertainty (phase 3).
4. **No PyTorch in v1:** sklearn + numpy only. This is a deliberate frugality
   decision matching the thesis's *"frugal ML"* constraint.
5. **Edge export:** `EdgeLoader`/`export_edge_model` produces JSON+numpy
   formats runnable without sklearn at runtime.

## 11. Data Engine Evaluation

**Primary identity:** Data Engine is **all of the above** — a processing
framework (pipeline orchestration), a geospatial analytics engine (radiation/
energy-balance physics), a remote-sensing workflow system (Landsat + Sentinel
pipelines), and a feature-generation platform (NDVI, albedo, emissivity,
roughness, stress indices, ET products).

The `rsmetric-library` spec formalizes the two-domain structure:

- `data_engine.landsat` — full METRIC ETa pipeline
- `data_engine.sentinel` — Sentinel-2 processing
- Shared top-level modules: `core`, `io`, `utils`, `surface`, `radiation`,
  `energy_balance`, `et`, `preprocess`, `output`, `validation`, `calibration`,
  `weather`, `settings`

**Smallest useful version:** The `DataCube` + `METRICPipeline` with the shared
physics modules (`surface/vegetation.py` NDVI, `surface/albedo.py`,
`surface/emissivity.py`, `radiation/shortwave.py`, `radiation/longwave.py`,
`radiation/net_radiation.py`, `energy_balance/*`, `et/instantaneous_et.py`,
`et/daily_et.py`, `calibration/dt_calibration.py`). This can process one
Landsat scene → ET products. The `io/landsat_reader.py` + `io/meteo_reader.py`
+ `weather/fetch.py` (Open-Meteo) are the minimum input surface.

**Largest envisioned version** (extrapolating from the module tree and specs):

- Both Landsat **and** Sentinel domains, fully independent
- `io/planetary_computer_fetcher.py` — on-demand scene fetching from
  Microsoft Planetary Computer
- `preprocess/cloud_mask.py`, `preprocess/resampling.py` — full preprocessing
- `output/product_organizer.py`, `output/visualization.py` — artifact
  organization + maps
- `validation/integration.py`, `validation/comprehensive_validation.py` —
  radiation balance closure, energy balance closure, ET reasonableness checks
- `surface/salinity.py`, `surface/stress.py`, `surface/moisture.py`,
  `surface/productivity.py`, `surface/temporal_stress.py`, `surface/optram.py`
  — derived biophysical products beyond ET
- `et/quality.py` — quality classes and confidence maps
- Exposure as a geoagent tool (`rs_compute_et`) with artifact discipline,
  600s timeout, sandboxed paths

**Current reality:** It is a clone/integration of an external METRIC
repository (`archive/2026-09-15-rsmetric-clone-and-integration`). Tests
reference Windows-style scene paths (`D:\RS\Projects\...`). The
domain-separation spec (Landsat ↔ Sentinel must not import each other) is a
stated requirement but I could not verify it is mechanically enforced.

## 12. System-Level Vision (5-year horizon)

Synthesized from `CHARTER.md`, the roadmaps, and the data-flow diagram in
`ARCHITECTURE.md`.

```
                        ┌──────────────────────────────────────────────┐
                        │               HUMAN RESEARCHER               │
                        │   supervisor · reviewer · experiment designer │
                        └──────────────────┬───────────────────────────┘
                                           │ natural language, feedback, review
                                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                 APPS                                     │
│  web SPA (:5173) · CLI · MCP server · notebooks                        │
│  All consume ONLY the gateway HTTP API. No direct lib imports.         │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ REST / SSE / multipart
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                               GATEWAY                                    │
│  FastAPI, single worker, one active workspace, write lock              │
│  Background job registry · SSE event bus · /files sandbox              │
│  Composes: geomemory (public facade) + geoagent (registry + core)      │
└───────┬──────────────────────────────────────┬───────────────────────┘
        │                                      │
        ▼                                      ▼
┌──────────────────────┐            ┌──────────────────────────────────────┐
│   GEOAGENT           │            │   DATA ENGINE                         │
│  reasoning loop       │            │  Landsat + Sentinel pipelines        │
│  tool registry        │◄──────────│  METRIC ET · spectral indices        │
│  playbooks (fast path)│  rs_compute_et                    │
│  agent.db (own state) │                                   │
│  citations [S#]       │                                   │
└──────────┬───────────┘                                   │
           │ consumes predictions                          │
           ▼                                              │
┌──────────────────────┐                                   │
│   GEOLEARN           │                                   │
│  online classifiers  │                                   │
│  per (crop, region)   │                                   │
│  NN cold-start fallback│                                 │
│  confidence + abstain │                                   │
│  model versioning     │                                   │
│  geolearn.db (own)    │                                   │
└──────────┬───────────┘                                   │
           │ reads candidate_memory                         │
           ▼                                               │
┌─────────────────────────────────────────────────────────────────────────┐
│                              GEOMEMORY                                   │
│  ingest → segments → embeddings → hybrid search → grounded QA           │
│  candidate memories · entity profiles · research timelines              │
│  feedback events · review queue · eval datasets · provenance chain      │
│  geomemory.db (single writer, WAL) + objects/<sha256>                   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MODELS + STORAGE                                 │
│  GGUF LLMs · ONNX/OLMoEarth embedders · SQLite (FTS5/RTree/vec)        │
│  content-addressed object store · vector index manifests                 │
└─────────────────────────────────────────────────────────────────────────┘
```

**Information flow** (the platform's signature loop, `ARCHITECTURE.md`):

```
files ──ingest──▶ assets ──search/ask──▶ hits ──use──▶ citations
                     │                          │
                     │                    feedback event
                     ▼                          ▼
               segments ────────▶ review queue ──▶ export JSONL
               (embedded)              (accept/reject)      │
                     ▲                                        ▼
                     └────────── (GeoLearn) training data ──▶ models/labels flow back
```

**Ownership boundaries at 5 years:**

- **GeoMemory** is the immutable foundation: content identity, provenance,
  retrieval, candidate memory lifecycle. It gets an ANN backend, a real
  background worker, an MCP server, and multilingual support. It does not
  get an agent loop or a training system.
- **GeoAgent** is the reasoning layer: planning, tool selection,
  citation-grounded generation, playbook replay. It gets an MCP exposure and
  possibly multi-agent orchestration, but never model training.
- **GeoLearn** is the adaptation layer: online classifiers, confidence
  calibration, region/personalization profiles, edge export. It gets drift
  detection and replay buffers, but never retrieval or agent logic.
- **Data Engine** is the physics layer: EO processing pipelines. It gets both
  Landsat and Sentinel domains fully independent, plus more biophysical
  products, but never memory or learning.
- **Gateway** remains the single HTTP surface, composing public facades only.

**Learning loops:**

1. **Feedback loop:** user marks answer/stress class wrong → `feedback_event`
   → review queue → accept → `candidate_memory` (verified) → GeoLearn
   `partial_fit` → updated classifier → better predictions next time.
2. **Reasoning loop:** user asks question → GeoAgent plans → `geo_search`
   (GeoMemory) → `geo_compute_indices`/`geo_zonal_stats` (Data Engine via
   GeoAgent) → LLM cites `[S#]` → answer. Repeated workflows get saved as
   playbooks → deterministic fast path (zero LLM latency).
3. **Evaluation loop:** `geomemory eval run` over fixed benchmarks →
   regression gate in CI → detects retrieval/QA regressions across versions.

**Role of humans:**

- **Supervisor** — chats for irrigation/fertilization/spraying guidance;
  confirms or rejects recommendations (*"automatic prescription without
  human confirmation"* is explicitly a non-goal).
- **Reviewer** — accepts/rejects dataset examples in the review queue; this
  is the human input that drives the learning loop.
- **Experiment designer** — creates workspaces, ingests sources, configures
  LLM/embedding providers, designs case studies in `studies/`.
- **Developer** — adds tools and playbooks without touching the harness.

The system is designed so that **the human is never bypassed on normative
claims** — every recommendation carries `[S#]` citations traceable to raw
bytes, and data gaps produce explicit abstention, not silent guesses.

## 13. Architectural Confidence

**Stable / unlikely to change:**

1. **Content identity = SHA-256 + provenance chain**
   (`answer → citation → segment → asset_revision → objects/<sha256>`). This
   is the platform's core identity axiom, inherited from GeoMemory
   invariants, backed by ADR-0003 and ADR-0007. It is too fundamental to
   revisit.
2. **Facade-only consumption** (`geomemory/__init__.py` as the stability
   boundary). Backed by ADR-0004, the black-box test suite, and the
   dashboard's enforced contract. The v1.0 "stability contract" will
   formalize it.
3. **Protocol-based extensibility** (`TextEmbedder`, `VisionEmbedder`,
   `RetrievalBackend`, `LLMBackend`). These seams are designed for exactly
   this — they are the answer to "what if the embedder changes," not a
   temporary pattern.
4. **Single SQLite writer + one active workspace + asyncio write lock.**
   This is a platform invariant (`state.py`), not an implementation detail.
   It constrains deployment topology permanently.
5. **Pydantic v2 domain models everywhere.** Backed by ADR-0004. The gateway
   returns libs' models directly — this contract is load-bearing.
6. **The downward dependency direction** (CHARTER's "one architectural
   rule"). It is the right rule even if unenforced. I am confident the
   *direction* is correct; I am not confident it will be mechanically
   preserved.
7. **Abstention over hallucination** as a first-class outcome. Backed by
   ADR-0007 and the `NullBackend` design. This is a value, not a pattern,
   and it is settled.

**Experimental / likely to change:**

1. **GeoLearn is entirely experimental.** It is 0.1.0, brand new, and every
   component (EmbeddingCache, OnlineClassifier, ConfidenceModel,
   ClassifierStore, PredictionResult) is a first draft. The entire phase-3
   roadmap (11 more changes) is unbuilt. The `(crop_type, region)` keying
   scheme, the 30-sample NN threshold, the 0.6 confidence threshold, and the
   SGDClassifier choice are all design decisions that could be replaced.
2. **The vision embedding path.** `PlaceholderVisionEmbedder` is a stub; the
   OLMoEarth GGUF path is experimental. The entire multimodal search
   capability is provisional.
3. **The embedding model strategy.** ADR-0002 chose GGUF via llama-cpp, but
   the actual canonical lightweight path is ONNX Xenova. The
   `storage-architecture` spec names sentence-transformers + LanceDB as
   defaults; the code uses sqlite-vec + ONNX. This drift is unresolved and
   could flip.
4. **Data Engine domain separation.** The Landsat ↔ Sentinel isolation is a
   spec requirement on a codebase cloned from an external repo with Windows
   paths. I cannot confirm it is enforced.
5. **The `[rs]` extra bundling `["geolearn", "data-engine"]` in geoagent.**
   This is a new coupling that couples release cycles. It is documented as
   intentional but is a deviation from clean layering.
6. **GeoAgent's cloud-first LLM decision.** The `LLMBackend` protocol seam
   is reserved for local runtimes but none ships. If the thesis requires
   offline LLM, this changes fundamentally.

**Highest-risk architectural decisions (if wrong, force major redesign):**

1. **GeoLearn's direct SQLite read of `geomemory.candidate_memory`.** This
   is the single most dangerous precedent. It breaks the facade-only
   invariant that geoagent and the dashboard respect, and it creates a
   hidden, unversioned, undocumented coupling between two independently-
   versioned libraries. If `candidate_memory` schema changes, GeoLearn
   breaks silently. **Mitigation needed:** route through the GeoMemory
   public facade (a `list_candidate_memories()` method), or formally
   document and version the internal contract. Right now it is justified by
   a spec note, not by a mechanism.
2. **`geoagent → geolearn` is an upward dependency** relative to CHARTER's
   layer model (LEARNING above APPLICATION). The actual import graph is
   `geoagent → geolearn → geomemory`, which inverts the intended
   `geoagent → geomemory` direct edge. If the layer model is the intended
   truth, this must be reversed (GeoLearn invokes GeoAgent, not vice versa)
   or the layer model must be revised. **This is a live inconsistency
   between spec and code.**
3. **Single SQLite writer with no retry/backoff.** `ADR-0003` explicitly
   flags *"concurrent writers across processes risk `SQLITE_BUSY`
   (unhandled retry logic today)"* and `gap-analysis` lists it as a
   bottleneck. The platform's deployment topology (one gateway container,
   one workspace) is built on this assumption. If a second process ever
   needs write access (a background worker, a CLI while the dashboard is
   open), the entire serialization model must be rethought. The v0.1
   roadmap adds a *"SQLite busy-retry/backoff helper"* but it is not yet
   done.
4. **The facade god-object** (`core/workspace.py`, 1152 LOC). It mixes
   orchestration and inline SQL, and it is the highest fan-out module in the
   system. Every consumer funnels through it. A breaking change to the
   facade is a breaking change to the platform. The v0.1 plan to *"extract
   inline SQL into repositories; split facade into composition of services"*
   is the right fix but is not yet executed. Until then, the facade is a
   single point of architectural fragility.
5. **No CI enforcement of any quality gate.** ruff, mypy `--strict`, pytest,
   and coverage ≥80 are *"configured, not yet CI-enforced."* There is no
   automated check that the downward-dependency rule holds, that consumers
   import only public facades, or that the OpenSpec specs match the code.
   **Every architectural invariant in this document is currently upheld by
   convention and prose, not by tooling.** This is the meta-risk: the
   architecture is well-specified but not mechanically protected.
6. **The "one active workspace" assumption.** The gateway holds exactly one
   workspace (`state.py`). The web app has a workspace switcher in the
   header (`SPEC_WEB.md`), but the gateway can only serve one at a time. If
   the product ever needs concurrent workspaces (multi-project research,
   A/B comparison), the gateway's state model must be fundamentally
   redesigned — it is currently a singleton `AppState`.
7. **Data Engine is a clone, not an original design.** It was integrated
   from an external METRIC repository
   (`archive/2026-09-15-rsmetric-clone-and-integration`). The domain-
   separation spec and the shared-module structure were imposed after the
   fact. The test suite references Windows paths. This is not necessarily a
   problem, but it means the library's internal structure is a reflection of
   its provenance, not a clean architectural choice, and the Landsat/
   Sentinel isolation may not be as clean as the spec claims.

## 14. Appendix: Normative references

- `CHARTER.md` — vision, layer model, core values, roadmap
- `STRUCTURE.md` — artifact taxonomy, conda env, subtree note, case-study
  pattern, versioning, git hygiene
- `SPEC_SERVER.md` — gateway HTTP API v1 spec (the only surface apps consume)
- `SPEC_WEB.md` — web app spec + milestones
- `libs/geomemory/AGENTS.md` — GeoMemory guidance and key invariants
- `libs/geomemory/docs/adr/` — ADR-0001 (vector search), ADR-0002
  (embedding model strategy), ADR-0003 (storage architecture), ADR-0004
  (public API design), ADR-0005 (hybrid retrieval fusion), ADR-0006
  (local-first offline), ADR-0007 (grounded QA provenance)
- `libs/geomemory/docs/gap-analysis.md` — current implementation vs goals
- `libs/geomemory/docs/roadmap.md` — proposed capability milestones
- `libs/geomemory/docs/library-capabilities.md` — comprehensive capability
  guide
- `libs/geoagent/openspec/project.md` — GeoAgent project context and
  decisions
- `libs/geoagent/openspec/specs/*` — agent-core, tool-registry, memory-tools,
  gis-tools, advisor, playbooks, learning-loop, mcp-interface
- `libs/geolearn/openspec/changes/archive/2026-09-10-*` — GeoLearn specs
  (core-framework, feedback-to-training-pipeline, online-learning-engine,
  frozen-foundation-model-adapters, personalization-profiles,
  region-specific-adaptation, incremental-embedding-learning,
  lightweight-classifier-layer, model-versioning-and-rollbacks,
  confidence-and-uncertainty-modeling, edge-deployment-runtime)
- `libs/geolearn/docs/phase3-roadmap.md` — GeoLearn phase 3 roadmap
- `libs/data_engine/openspec/changes/archive/2026-09-15-*` — Data Engine
  integration specs (rsmetric-library, geoagent-rs-tool, sample-pipeline,
  optram-surface-index, data-engine-io-complete, web-app, gateway-server,
  model-auto-download, pending-changes-completion)
- `libs/data_engine/src/data_engine/README.md` — METRIC ETa pipeline
  documentation
