## ADDED Requirements

### Requirement: Facade query for candidate memories
The `GeoMemory` public facade SHALL expose a typed method to query candidate memories by lifecycle state and temporal criteria, returning a list of `CandidateMemory` Pydantic models.

#### Scenario: Query verified candidates
- **WHEN** an external library calls `ws.list_candidate_memories(states=["verified", "supported"])`
- **THEN** matching `CandidateMemory` instances are returned without requiring raw database access
