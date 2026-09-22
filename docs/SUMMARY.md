# GeoFoundation — Architecture Summary

> Condensed version of `ARCHITECTURE.md`. For full detail, read that document.
> Current state: post-MSc thesis phase. All libraries at v0.1.0.

## The one rule

**Dependencies point strictly downward.**

```
APPS → GATEWAY → geoagent + data_engine → geolearn → geomemory → models → storage
```

Apps never import libs directly. The gateway imports only public facades. Libs
never import upward.

## The four libraries

| Library | Layer | Owns |
|---|---|---|
| `geomemory` | MEMORY | Ingest, segments, embeddings, hybrid search, grounded QA, candidate memories, entity profiles, research timelines, feedback events, eval datasets, provenance |
| `geoagent` | APPLICATION | Agent harness, tool registry, planning, tool selection, citations, playbooks, agent.db (own state) |
| `geolearn` | LEARNING | Online classifiers per (crop, region), confidence, NN cold-start fallback, model versioning, edge export, geolearn.db (own state) |
| `data_engine` | APPLICATION | Landsat + Sentinel METRIC ETa pipelines, spectral indices, energy-balance physics |

## What each must never do

- **GeoMemory**: never run an agent loop, never host HTTP/MCP, never train
  models, never write its own DB from outside the facade, never mix embedding
  spaces across modalities, never fabricate.
- **GeoAgent**: never write GeoMemory's DB directly, never own knowledge
  storage (separate `agent.db`), never do local LLM runtimes in v0.x, never
  train ML models, never fabricate citations, never bypass the registry.
- **GeoLearn**: never use PyTorch in v1, never do retrieval/ranking, never
  write to GeoMemory, never host an agent loop.
- **Data Engine**: never couple Landsat ↔ Sentinel domains, never be an
  agent/memory/learning system, never mutate shared state.

## Knowledge ownership (quick reference)

| Concept | Owner |
|---|---|
| Documents, segments, embeddings, candidate memories, entity profiles, relations, feedback events, eval datasets, research timelines, raster scene metadata, NDVI/EVI | **GeoMemory** |
| Learned models (classifiers, versions), feedback learning | **GeoLearn** |
| Agent memories (conversations), task plans, tool execution history | **GeoAgent** |
| ET outputs, spectral index tools (NDWI/SAVI wrappers) | **Data Engine** (ET), **GeoAgent** (tools) |

## Two known architectural deviations

1. **`geoagent → geolearn` is upward** relative to the CHARTER layer model.
   CHARTER puts LEARNING above APPLICATION, but
   `geoagent/tools/geolearn_tools.py` imports `geolearn`. The actual chain is
   `geoagent → geolearn → geomemory`, inverting the intended
   `geoagent → geomemory` direct edge.
2. **`geolearn` reads `geomemory` via raw SQLite, not the facade.**
   `training_pipeline.py:49-91` opens `geomemory.db` directly and runs
   `SELECT ... FROM candidate_memory`. This breaks the facade-only invariant
   that geoagent and the dashboard respect, and creates a hidden coupling
   between two independently-versioned libraries.

## Seven highest-risk decisions

1. **GeoLearn's direct-SQL read of `candidate_memory`** — breaks the
   facade-only invariant; if the schema changes, GeoLearn breaks silently.
2. **`geoagent → geolearn` upward dependency** — live inconsistency between
   spec and code.
3. **Single SQLite writer with no retry/backoff** — `SQLITE_BUSY` risk if a
   second process ever needs write access.
4. **Facade god-object** (`core/workspace.py`, 1152 LOC) — single point of
   architectural fragility; every consumer funnels through it.
5. **No CI enforcement of any quality gate** — every invariant is currently
   upheld by convention and prose, not by tooling.
6. **"One active workspace" assumption** — the gateway holds exactly one
   workspace; concurrent workspaces would force a redesign.
7. **Data Engine is a clone, not an original design** — integrated from an
   external METRIC repo with Windows-path tests; domain separation may not be
   as clean as the spec claims.

## Stable vs. experimental

**Stable:** SHA-256 content identity + provenance chain; facade-only
consumption; protocol-based extensibility; single SQLite writer + one active
workspace; Pydantic v2 domain models; downward dependency direction;
abstention-over-hallucination as a first-class outcome.

**Experimental:** GeoLearn (entirely 0.1.0, 11 more phase-3 changes unbuilt);
vision embedding path (`PlaceholderVisionEmbedder` stub); embedding model
strategy (spec says sentence-transformers/LanceDB, code uses ONNX/sqlite-vec);
Data Engine domain separation; the `[rs]` extra bundling geolearn + data-engine;
GeoAgent's cloud-first LLM decision.

## Where to read more

- `docs/ARCHITECTURE.md` — full 14-section assessment
- `docs/CHARTER.md` — vision, layer model, core values, roadmap
- `docs/STRUCTURE.md` — conventions, conda env, versioning, git hygiene
- `docs/SPEC_SERVER.md` — gateway HTTP API v1 (the only surface apps consume)
- `docs/SPEC_WEB.md` — web app spec + milestones
- `libs/geomemory/docs/adr/` — ADR-0001 through ADR-0007
- `libs/geomemory/docs/gap-analysis.md` and `roadmap.md`
- `libs/geoagent/openspec/project.md` and `openspec/specs/*/spec.md`
- `libs/geolearn/openspec/changes/archive/2026-09-10-*` and `docs/phase3-roadmap.md`
- `libs/data_engine/openspec/changes/archive/2026-09-15-*`