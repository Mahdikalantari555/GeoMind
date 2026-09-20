## Why

The server gateway (`server/src/geofront_api/`) imports internal geomemory classes in 7+ router files, violating the core architectural invariant documented in both `AGENTS.md` and `libs/geomemory/AGENTS.md`: "gateway imports only public facades, never internals." This coupling means any refactor in geomemory's storage, services, or feedback modules becomes a breaking change for the server — preventing independent evolution and making the geomemory black-box test suite insufficient to protect the integration boundary. Additionally, two classes named `SearchService` exist (one thin wrapper dropping params, one full implementation), creating API confusion.

## What Changes

- Add public facade methods to `GeoMemory` (in `libs/geomemory/src/geomemory/core/workspace.py`) covering all operations currently accessed via internal imports:
  - `ws.list_entities(kind?)` → replaces `EntityRepository` direct usage
  - `ws.get_entity_profile(name)` → replaces `EntityProfileService` direct usage
  - `ws.get_research_timeline(project, ...)` → replaces `ResearchTimelineService` direct usage
  - `ws.create_candidate_memory(content, memory_type, ...)` → replaces `CandidateMemoryService` direct usage
  - `ws.create_proposal(...)` → replaces `ProposalEngine` direct usage
  - `ws.list_available_models()` → replaces `EmbeddingModelHub` direct usage
  - `ws.download_model(name, backend)` → replaces `download_vision_model` direct usage
- Remove all internal imports from server router files (`entities.py`, `ask.py`, `memory.py`, `feedback.py`, `index.py`, `models.py`)
- Unify the double `SearchService`: either delete the thin wrapper in `services/search_service.py` or make it delegate fully with all params (modalities, modality_weight)
- Ensure geomemory's public facade (`__init__.py`) exports all new methods

## Capabilities

### New Capabilities
- `public-service-boundary`: The server gateway SHALL access geomemory exclusively through the `GeoMemory` public facade; no internal module imports (storage.repositories, services.*, feedback.*, embeddings.*, qa.*) are permitted in server source code.

### Modified Capabilities
- `geomemory-facade`: The `GeoMemory` class SHALL expose all operations required by the server gateway as public methods, preserving existing behavior while adding new entry points for entity management, research timelines, candidate memory creation, proposals, and model management.

## Impact

| Area | Detail |
|---|---|
| `libs/geomemory/src/geomemory/core/workspace.py` | Add ~7 new public methods to `Workspace`/`GeoMemory` |
| `libs/geomemory/src/geomemory/__init__.py` | Export any new models used by new facade methods |
| `server/src/geofront_api/routers/entities.py` | Remove `from geomemory.storage.repositories.entity_repo import EntityRepository` |
| `server/src/geofront_api/routers/ask.py` | Remove internal `CandidateMemoryService`, `TurnRepository` imports |
| `server/src/geofront_api/routers/memory.py` | Remove internal service imports |
| `server/src/geofront_api/routers/feedback.py` | Remove internal service imports (x6 occurrences) |
| `server/src/geofront_api/routers/index.py` | Remove `EmbeddingModelHub` internal import |
| `server/src/geofront_api/routers/models.py` | Remove internal hub/download imports |
| `libs/geomemory/src/geomemory/services/search_service.py` | Delete or unify with `retrieval/search_service.py` |
| Tests | Verify geomemorytest black-box suite still passes; add server-side tests for new facade methods |
