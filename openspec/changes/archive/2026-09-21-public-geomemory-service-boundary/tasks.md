## 1. Facade method additions to Workspace

- [x] 1.1 In `libs/geomemory/src/geomemory/core/workspace.py`, add `list_entities(kind: str | None = None) -> list[Entity]` that delegates to `EntityRepository`; verify with a unit test in `tests/unit/`
- [x] 1.2 Add `get_entity_profile(name: str) -> dict[str, Any]` delegating to `EntityProfileService`; verify behavior matches current server response shape
- [x] 1.3 Add `get_research_timeline(project: str, *, memory_types, as_of, offset, limit) -> dict[str, Any]` delegating to `ResearchTimelineService`
- [x] 1.4 Add `create_candidate_memory(content, memory_type, source_feedback_ids, author) -> CandidateMemory` delegating to `CandidateMemoryService`
- [x] 1.5 Add `create_proposal(proposal_type, diff, source_candidate_ids, confidence) -> KnowledgeChangeProposal` delegating to `ProposalEngine`
- [x] 1.6 Add `list_available_models() -> list[dict[str, Any]]` delegating to `EmbeddingModelHub.scan()`
- [x] 1.7 Add `download_model(name: str, backend: str) -> dict[str, Any]` delegating to hub/download functions
- [x] 1.8 Ensure all new methods use lazy imports for heavy optional deps (geopandas, rasterio, etc.)
- [x] 1.9 Export any new Pydantic models from `libs/geomemory/src/geomemory/__init__.py` if they are return types of new facade methods
- [x] 1.10 In `server/src/geofront_api/services/agent.py`, add a public `@property workspace_path(self) -> Path | None` returning `self._workspace_path`; in `server/src/geofront_api/routers/agent/files.py`, replace all three `service._settings.workspace` occurrences (lines 20, 40, 67) with `service.workspace_path` and remove the `# type: ignore[union-attr]` comments

## 2. SearchService unification

- [x] 2.1 Decide: delete `geomemory/services/search_service.py` OR make it a proper delegate. Recommend deletion per design doc.
- [x] 2.2 If deleting: grep all callers across the monorepo (`grep -rn "from geomemory.services.search_service\|geomemory.services.search_service"`) and update to use the retrieval-layer class or `Workspace.search()` directly
- [x] 2.3 Verify `Workspace.search()` correctly passes `modalities` and `modality_weight` through to the retrieval service

## 3. Server router refactoring

- [x] 3.1 `server/src/geofront_api/routers/entities.py`: Replace `EntityRepository(ws.conn)` with `ws.list_entities(kind)` and `ws.traverse(entity_id)` (already exists)
- [x] 3.2 `server/src/geofront_api/routers/ask.py`: Replace `CandidateMemoryService(ws.conn)` and `TurnRepository(ws.conn)` with `ws.create_candidate_memory(...)` — note: turn lookup may need a separate facade method `ws.get_turn(turn_id)`
- [x] 3.3 `server/src/geofront_api/routers/memory.py`: Replace `EntityProfileService(ws.conn)` with `ws.get_entity_profile(name)` and `ResearchTimelineService(ws.conn)` with `ws.get_research_timeline(...)`
- [x] 3.4 `server/src/geofront_api/routers/feedback.py`: Replace all `CandidateMemoryService(ws.conn)` and `ProposalEngine(ws.conn)` calls with facade methods
- [x] 3.5 `server/src/geofront_api/routers/index.py`: Replace `EmbeddingModelHub` import with `ws.list_available_models()`
- [x] 3.6 `server/src/geofront_api/routers/models.py`: Replace `EmbeddingModelHub` and `download_vision_model` imports with `ws.list_available_models()` and `ws.download_model()`
- [x] 3.7 Remove all `from geomemory.*` imports that reference internal modules (not `geomemory` top-level or `geomemory.core.*`)

## 4. Verification

- [x] 4.1 Run `conda run -n geospatial pytest libs/geomemory/tests -q --tb=short` — expect 503 passed
- [x] 4.2 Run `conda run -n geospatial pytest libs/geomemory/geomemorytest/ -q --tb=short` — verify black-box suite passes
- [x] 4.3 Run `conda run -n geospatial pytest server/tests -q --tb=short` — all existing tests must pass without modification
- [x] 4.4 Run `conda run -n geospatial ruff check server/src libs/geomemory/src` — no new violations
- [x] 4.5 Run `cd apps/web && pnpm gen:api && pnpm build` — client generation and build must succeed
- [x] 4.6 Grep server source for prohibited internal imports: `grep -rn "from geomemory\\.storage\\|from geomemory\\.services\\|from geomemory\\.feedback\\|from geomemory\\.embeddings\\|from geomemory\\.qa\\|from geomemory\\.index\\|from geomemory\\.retrieval" server/src` — expect zero results (except `geomemory.core.exceptions` and `geomemory.core.models` which are public)

## 5. Documentation

- [x] 5.1 Update `docs/SPEC_SERVER.md` to document the new facade-dependent behavior (no internal imports)
- [x] 5.2 Update `tasks/todo.md` checkboxes to reflect completion status
