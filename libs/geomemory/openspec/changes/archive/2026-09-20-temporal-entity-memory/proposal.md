# Proposal: temporal-entity-memory

## Why

GeoMemory has a retrieval engine and a candidate-memory review pipeline (v0.1), but it cannot answer the questions that matter to a researcher over time:

- "What did I believe about OPTRAM in March 2025?"
- "Show me every decision and hypothesis for the DSPIT project on one timeline."
- "Everything known about Landsat-9 in one view."

The current schema models **documents and chunks** well, but not **facts as versioned, entity-linked beliefs**. Every capability below — temporal queries, knowledge evolution, entity profiles, research timelines — flows from closing that single gap. Nothing requires a new infrastructure class; everything is SQLite columns and endpoints on top of existing `candidate_memory`, `entity`, and `relation` tables.

## What Changes

### 1. Extend `candidate_memory` with temporal fields

Three columns added, zero new tables:

| Column | Type | Purpose |
|---|---|---|
| `observed_at` | TEXT (nullable ISO) | When the belief was true/held — may differ from when we learned it |
| `superseded_by` | TEXT FK → `candidate_memory.id` | Points to the row that replaced this one (for belief revision chains) |
| `project` | TEXT (nullable) | Project label: `'DSPIT'`, `'PIDL'`, etc. — powers research-timeline filtering |

Existing fields (`id`, `content`, `memory_type`, `confidence_score`, `state`, `audit_trail`, `source_feedback_ids`, `author`, timestamps) are untouched. Migration v2 appends columns to the existing table.

**Query pattern enabled**: `WHERE id = ? AND observed_at <= ? ORDER BY observed_at DESC LIMIT 1` gives "as-of" reads. No new index type — just a composite B-tree on `(id, observed_at)`.

### 2. Entity-linked views on existing `entity` / `relation` tables

No schema changes to `entity` or `relation`. Instead:

- A new service `EntityProfileService` joins `candidate_memory` rows to `entity` via `candidate_memory.content` text-matched against `entity.name` (seeded alias list: OPTRAM, NDVI, Landsat, Sentinel-1/2, salinity, Khuzestan, Farm 183…). No auto-NER yet.
- A lookup index `entity_lookup(candidate_memory_id → entity_id[])` is a materialized view (simple SELECT from `relation` where either endpoint matches the memory's project/entities). Stored as a helper query, not a new table.

Entities remain manual-first; extraction is a future enhancement.

### 3. Three additive API endpoints

| Endpoint | Capability |
|---|---|
| `GET /api/v1/memory/items/{uid}?as_of=…` | Temporal "as-of" read |
| `GET /api/v1/memory/entities/{name}` | Entity profile: current beliefs, history, related entities |
| `GET /api/v1/research/timeline?project=DSPIT&type=decision,hypothesis` | Project research timeline |

All additive — existing `/search`, `/ask`, `/feedback/candidates` unchanged.

### 4. Retrieval enhancements (opt-in, backwards-compatible)

- `status='superseded'` rows excluded from default hybrid search; `include_superseded=true` re-enables them.
- Entity name in query text boosts FTS5 hits joined to matching `entity` rows (score weighting, not a new retrieval path).

## Capabilities

### Modified Capabilities
- `candidate-memory-store`: adds `observed_at`, `superseded_by`, `project` columns; new "as-of" read method.
- `evolutionary-memory`: adds entity-profile and research-timeline query paths; spatial/temporal/sensor filters already exist via `retrieval/search_service.apply_hit_filters`.
- `storage-persistence`: migration v2 adds three nullable columns to `candidate_memory`; no data migration required.

### New Capabilities
- `temporal-memory`: point-in-time reads on `candidate_memory` via `observed_at` filter.
- `entity-profiles`: `GET /memory/entities/{name}` joining existing `entity`/`relation` to `candidate_memory`.
- `research-timelines`: filtered chronological view of `candidate_memory` by `project` + `memory_type`.

## Impact

- **Code**: `src/geomemory/core/models.py` (+3 fields on `CandidateMemory`), `src/geomemory/storage/schema.sql` (migration v2), `src/geomemory/feedback/candidate_memory.py` (new methods), new `src/geomemory/services/entity_profile_service.py`, new `src/geomemory/services/research_timeline_service.py`, `server/src/geofront_api/routers/memory.py` (new router), optional `apps/web` UI pages.
- **APIs**: 3 new routes under `/api/v1/memory/` and `/api/v1/research/`; no breaking changes to existing routes.
- **Deps**: none new.
- **Risks**: seed alias list must be curated per-user (out of scope for default); `observed_at` population requires caller awareness — defaults to `created_at` if unset.

## Non-Goals (explicitly deferred)

- Contradiction detection (semantic scan, LLM-judged conflicts)
- Knowledge consolidation / rollup summaries
- Entity extraction (NER) — seeded alias matching only
- Agent memory types (episodic/working/semantic taxonomy)
- Graph visualization UI
- Automatic temporal backfill of existing records (manual `observed_at` setting only)
