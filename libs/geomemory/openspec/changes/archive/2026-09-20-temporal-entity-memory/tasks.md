## 1. Schema migration v2 — add three columns to `candidate_memory`

- [x] 1.1 Edit `src/geomemory/storage/schema.sql`: add a migration v2 block that runs `ALTER TABLE candidate_memory ADD COLUMN observed_at TEXT`, `ADD COLUMN superseded_by TEXT REFERENCES candidate_memory(id) ON DELETE SET NULL`, `ADD COLUMN project TEXT`; widen the CHECK on `memory_type` to include `decision|hypothesis|method|dataset_event|episodic|working` (or remove the CHECK and let application logic enforce valid values — prefer widening for auditability). Add composite index `CREATE INDEX IF NOT EXISTS idx_candidate_observed ON candidate_memory(id, observed_at DESC)`.
- [x] 1.2 Update `src/geomemory/storage/migrations.py`: register migration v2 with description "add temporal/entity fields to candidate_memory". Ensure idempotent (IF NOT EXISTS / column-existence guard).
- [x] 1.3 Verify: run migration against a clean workspace DB; `PRAGMA table_info(candidate_memory)` shows the three new columns; `PRAGMA foreign_key_list(candidate_memory)` confirms the FK.

## 2. Extend `CandidateMemory` model + repository

- [x] 2.1 Edit `src/geomemory/core/models.py`: add `observed_at: str | None = None`, `superseded_by: str | None = None`, `project: str | None = None` to `CandidateMemory` Pydantic model. Default `observed_at` serializes to `created_at` via a `model_validator` or property so existing callers are unaffected.
- [x] 2.2 Edit `src/geomemory/feedback/candidate_memory.py`: update `create()` to accept/insert the new fields; add `get_as_of(cm_id: str, as_of: str) -> CandidateMemory | None` that returns the latest version of the item whose `observed_at <= as_of`; add `mark_superseded(cm_id: str, by_id: str) -> None` (sets `superseded_by` on the old row); add `list_by_project(project: str, types: list[str] | None = None, offset: int = 0, limit: int = 50) -> list[CandidateMemory]`.
- [x] 2.3 Tests: `tests/unit/test_temporal_candidate_memory.py` — `get_as_of` returns correct version; `mark_superseded` sets FK correctly; `list_by_project` filters and paginates. Run `pytest tests/unit/test_temporal_candidate_memory.py -q`.

## 3. Seeded alias entity index + `EntityProfileService`

- [x] 3.1 Create `src/geomemory/services/entity_profile_service.py`: reads the alias list from `workspace.settings.entity_alias_index` (JSON array of strings) on construction; exposes `get_profile(entity_name: str) -> dict` returning `{name, kind, current_beliefs: [CandidateMemory], history: [CandidateMemory], related_entities: [str]}` where `current_beliefs` are active candidate memories whose content contains the alias (case-insensitive substring match), `history` includes superseded rows, and `related_entities` are other entities co-mentioned in the same memories (via `relation` table joins).
- [x] 3.2 Create a default seed alias list in code: `DEFAULT_ENTITY_ALIASES = ["OPTRAM", "NDVI", "Landsat", "Sentinel-1", "Sentinel-2", "salinity", "Khuzestan", "Farm 183", ...]` — document that users extend via workspace settings.
- [x] 3.3 Tests: `tests/unit/test_entity_profile_service.py` — profile for known entity returns linked memories; unknown entity returns empty list; alias collision returns both links.
- [x] 3.4 No schema change needed — aliases live in `workspace.settings`.

## 4. Research timeline service + route

- [x] 4.1 Create `src/geomemory/services/research_timeline_service.py`: exposes `get_timeline(project: str, memory_types: list[str] | None, as_of: str | None, offset: int, limit: int) -> dict` returning `{project, items: [CandidateMemory], total}` ordered by `observed_at DESC`.
- [x] 4.2 Add router `server/src/geofront_api/routers/memory.py` with two endpoints:
  - `GET /api/v1/memory/entities/{entity_name}` → calls `EntityProfileService.get_profile()`
  - `GET /api/v1/research/timeline?project=X&type=Y&as_of=Z&offset=0&limit=50` → calls `ResearchTimelineService.get_timeline()`
- [x] 4.3 Register router in `server/src/geofront_api/main.py`.
- [x] 4.4 Regenerate API client: `cd apps/web && pnpm gen:api`. Fix any TS type errors.
- [x] 4.5 Tests: `server/tests/test_memory_router.py` — 200 response shapes, 404 for unknown entity, pagination boundary checks.

## 5. Retrieval filter — exclude superseded by default

- [x] 5.1 In `src/geomemory/retrieval/search_service.py` (or wherever candidate memories enter the RRF fusion), add an optional `include_superseded: bool = False` parameter; when false, filter out `candidate_memory` rows where `status='superseded'` before scoring. Pass through from any new endpoint that needs it; existing `/ask` keeps default behavior.
- [x] 5.2 Tests: `tests/retrieval/test_superseded_excluded.py` — query that would match a superseded memory does not return it unless `include_superseded=true`.

## 6. Gates

- [x] 6.1 Full test suite: `conda run -n geospatial pytest libs/geomemory/tests server/tests -q` (621 passed, 8 skipped).
- [x] 6.2 Lint and type-check: `conda run -n geospatial ruff check libs/geomemory/src server/src` passes; strict mypy passes for all changed modules. The repository-wide mypy command remains blocked by 65 pre-existing errors in untouched modules.
- [x] 6.3 Web build: `cd apps/web && pnpm lint && pnpm build && pnpm test` (lint 0 errors; build succeeded; 34 tests passed).

Dependencies: 1→2, 2→3,4,5, 3+4+5→6.
