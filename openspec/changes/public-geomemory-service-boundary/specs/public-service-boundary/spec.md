## Purpose

Define the observable behavior of the geomemory public facade and the server boundary constraint, ensuring the gateway can operate without knowledge of geomemory internals.

## ADDED Requirements

### Requirement: Server SHALL use only GeoMemory public facade
The server gateway (`server/src/geofront_api/`) SHALL NOT import any module from `geomemory` beyond the top-level package exports declared in `libs/geomemory/src/geomemory/__init__.py`. Specifically, imports from `geomemory.storage`, `geomemory.services`, `geomemory.feedback`, `geomemory.embeddings`, `geomemory.qa`, `geomemory.index`, and `geomemory.retrieval` are PROHIBITED in server source files.

#### Scenario: Entity listing via facade
- **WHEN** a client calls `GET /api/v1/entities`
- **THEN** the server SHALL call `ws.list_entities(kind)` on the `GeoMemory` facade
- **AND** the response SHALL contain entity data identical to what `EntityRepository.list_by_workspace()` previously returned

#### Scenario: Entity profile via facade
- **WHEN** a client calls `GET /api/v1/memory/entities/{name}`
- **THEN** the server SHALL call `ws.get_entity_profile(name)` on the `GeoMemory` facade
- **AND** the response SHALL match the shape previously produced by `EntityProfileService.get_profile()`

#### Scenario: Research timeline via facade
- **WHEN** a client calls `GET /api/v1/research/timeline?project=...`
- **THEN** the server SHALL call `ws.get_research_timeline(project, ...)` on the `GeoMemory` facade
- **AND** the response SHALL match the shape previously produced by `ResearchTimelineService.get_timeline()`

#### Scenario: Candidate memory creation via facade
- **WHEN** a client calls `POST /api/v1/ask/{turn_id}/suggest`
- **THEN** the server SHALL call `ws.create_candidate_memory(content, memory_type, ...)` on the `GeoMemory` facade
- **AND** the response SHALL match the shape previously produced by `CandidateMemoryService.create()`

#### Scenario: Feedback proposal via facade
- **WHEN** a client calls `POST /api/v1/feedback/proposal`
- **THEN** the server SHALL call `ws.create_proposal(...)` on the `GeoMemory` facade
- **AND** the response SHALL match the shape previously produced by `ProposalEngine.create()`

#### Scenario: Model listing via facade
- **WHEN** a client calls `GET /api/v1/models`
- **THEN** the server SHALL call `ws.list_available_models()` on the `GeoMemory` facade
- **AND** the response SHALL match the shape previously produced by `EmbeddingModelHub.scan()`

#### Scenario: Model download via facade
- **WHEN** a client calls `POST /api/v1/models/download`
- **THEN** the server SHALL call `ws.download_model(name, backend)` on the `GeoMemory` facade
- **AND** the response SHALL match the shape previously produced by `download_vision_model()`

### Requirement: SearchService unification
There SHALL be exactly one authoritative `SearchService` class. The thin wrapper in `geomemory/services/search_service.py` SHALL either be deleted (all callers routed through `geomemory/retrieval/search_service.SearchService`) OR updated to delegate all parameters including `modalities` and `modality_weight`.

#### Scenario: Multimodal search params reach the retrieval layer
- **WHEN** `Workspace.search()` is called with `modalities="both"` and `modality_weight=0.8`
- **THEN** these parameters SHALL be passed through to the underlying retrieval service without being dropped
- **AND** the result SHALL include image hits weighted by the provided modality weight

### Requirement: Public facade completeness audit
A post-change audit SHALL verify that every server route's behavior is preserved after refactoring through the public facade. All existing server tests (`server/tests/`) SHALL continue to pass without modification.

#### Scenario: No behavior regression in existing endpoints
- **WHEN** all existing server tests are run after the refactor
- **THEN** all tests SHALL pass with identical assertions and response shapes
- **AND** no new error codes or response field changes SHALL be introduced

## MODIFIED Requirements

### Requirement: geomemory public API surface
The `GeoMemory` class (exported from `geomemory.__init__`) SHALL gain the following new public methods with the signatures and behaviors specified below.

#### Method: `GeoMemory.list_entities(kind: str | None = None) -> list[Entity]`
Returns workspace entities, optionally filtered by `kind`. Behavior matches current `EntityRepository.list_by_workspace()` and `list_by_kind()`.

#### Method: `GeoMemory.get_entity_profile(name: str) -> dict[str, Any]`
Returns entity profile data including current beliefs, history, and related entities. Behavior matches current `EntityProfileService.get_profile()`.

#### Method: `GeoMemory.get_research_timeline(project: str, *, memory_types: list[str] | None = None, as_of: str | None = None, offset: int = 0, limit: int = 50) -> dict[str, Any]`
Returns project research timeline ordered by observed_at DESC. Behavior matches current `ResearchTimelineService.get_timeline()`.

#### Method: `GeoMemory.create_candidate_memory(content: str, memory_type: str = "correction", *, source_feedback_ids: list[str] | None = None, author: str | None = None) -> CandidateMemory`
Creates a new candidate memory entry. Behavior matches current `CandidateMemoryService.create()`.

#### Method: `GeoMemory.create_proposal(*, proposal_type: str, diff: dict, source_candidate_ids: list[str], confidence: float) -> KnowledgeChangeProposal`
Creates a knowledge change proposal. Behavior matches current `ProposalEngine.create()`.

#### Method: `GeoMemory.list_available_models() -> list[dict[str, Any]]`
Returns available embedding/vision models from the hub. Behavior matches current `EmbeddingModelHub.scan()`.

#### Method: `GeoMemory.download_model(name: str, backend: str) -> dict[str, Any]`
Downloads a model by name and backend. Behavior matches current `download_vision_model()` and `hub.find_model()`.
