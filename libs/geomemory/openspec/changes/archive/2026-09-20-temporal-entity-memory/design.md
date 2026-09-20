## Context

GeoMemory's `candidate_memory` table already holds content, confidence scores, state machines (proposed→supported→verified→rejected), audit trails, and source feedback links — but it treats every row as a point-in-time fact with no notion of *when* the fact was true versus *when* we learned it. A researcher updating their understanding over months (e.g., "OPTRAM works → OPTRAM has saline limitations → OPTRAM useful only under specific conditions") sees those revisions as separate rows with no chain linking them.

The existing schema also has an `entity` table (with `kind` constraint) and a `relation` table, but no service joins them to candidate memories — entities are manual annotations, not queryable hubs.

This change adds temporal fields to `candidate_memory` and two new services that surface entity profiles and research timelines, using only the tables that already exist.

## Goals / Non-Goals

**Goals:**
- `CandidateMemory` gains `observed_at`, `superseded_by`, and `project` — enabling "as-of" reads and project-scoped timeline queries.
- `GET /api/v1/memory/entities/{name}` returns current beliefs + full revision history for any known entity.
- `GET /api/v1/research/timeline?project=X&type=Y` returns a chronological view of decisions/hypotheses/methods for a project.
- Existing hybrid retrieval subtly prefers `status='active'` and excludes `superseded` rows without a breaking API change.
- Zero new SQLite tables; migration is three column additions to `candidate_memory`.

**Non-Goals:**
- Auto-extracting entities from text (seeded alias list only).
- Contradiction detection or automatic resolution.
- Consolidation / rollup summaries.
- Agent working-memory or episodic memory support.
- Graph traversal UI (D3/vis.js).
- Backfilling `observed_at` on existing records — left for future migration or explicit update.

## Decisions

### D1. Extend `candidate_memory`, do not create `memory_items`

The proposal in the plan docs suggests a new `memory_items` table as a "belief layer." `candidate_memory` already has every field needed (`content`, `memory_type`, `confidence_score`, `state`, `audit_trail`, `source_feedback_ids`, `author`). Adding `observed_at`, `superseded_by`, and `project` covers all query shapes without introducing a second copy of the same concept. Rationale: one fewer table to maintain, one fewer join, no data migration risk. The "belief layer" is a virtual concept surfaced by the service, not a physical table.

### D2. `observed_at` defaults to `created_at`, never auto-set

Callers (ingestion pipeline, agent writes, manual edits) set `observed_at` explicitly when they know when the belief became true. If unset, it defaults to `created_at` at read time via a COALESCE in SQL — never by a background job. This keeps the system honest: a fact inferred today about a 2023 experiment should not masquerade as being observed in 2023 unless the writer says so.

### D3. Entity matching uses a seeded alias index, not NER

The seed list (`OPTRAM`, `NDVI`, `Landsat`, `Sentinel-1`, `Sentinel-2`, `salinity`, `Khuzestan`, `Farm 183`, …) is stored as JSON in `workspace.settings.entity_alias_index`. `EntityProfileService` scans it on startup; a candidate memory whose `content` contains any alias is linked to that entity. No spaCy, no LLM NER. If an alias collision occurs (same text matches two entities), both links are kept — ambiguity is surfaced, not resolved automatically.

### D4. `superseded_by` is a self-referencing FK, not a status flag

A `status='superseded'` column alone cannot express *what* superseded a belief. `superseded_by TEXT REFERENCES candidate_memory(id)` lets the user traverse the chain (`row → superseded_by → superseded_by`) to see the full revision history. Setting it requires an explicit `PATCH /memory/items/{id} → {superseded_by: "another_id"}` call — no background job auto-supersedes.

### D5. Research timeline reuses `memory_type` values already in use

`candidate_memory.memory_type` currently supports `fact | correction | annotation | preference`. This change documents that values like `decision`, `hypothesis`, `method`, `dataset_event` are also valid (the CHECK constraint is widened). No new table; the timeline view is just `WHERE project=? AND memory_type IN (?) ORDER BY observed_at`.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `observed_at` left unset → temporal queries return nothing meaningful | Default to `created_at` at read time; document in migration notes that researchers should set it manually for historical facts. |
| Alias index grows large → string-scan latency | Index is small (<200 entries typically); scan is O(n) on aliases, not on memories. If it grows, convert to FTS5 later — don't pre-optimize. |
| `superseded_by` creates orphan chains if source row deleted | `ON DELETE SET NULL` on the FK; supersession link is lost gracefully, row still readable. |
| Timeline endpoint loads too many rows for large projects | Paginated (`?offset=&limit=`); default `limit=50`. Web UI infinite-scrolls; CLI shows a summary count first. |
| Entity profile joins are slow on unindexed content | `candidate_memory.content` is never indexed for full-text search within this change (FTS5 stays on `segment`); entity linking is alias-based, not content-search. |

## Verification

- **Schema**: `PRAGMA table_info(candidate_memory)` confirms three new columns after migration v2.
- **Unit — temporal read**: `tests/test_temporal_candidate_memory.py` asserts `as_of` query returns the correct version.
- **Unit — entity profile**: `tests/test_entity_profile_service.py` asserts alias-linked memories are returned; unlinked entities return empty profile.
- **Unit — research timeline**: `tests/test_research_timeline.py` asserts ordering, filtering by `memory_type`, and pagination.
- **Integration**: existing `pytest libs/geomemory/tests` passes; `ruff check src`; `mypy --strict src`.
- **Gateway**: `server/tests` passes with new routes verified via test client.
