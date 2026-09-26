## MODIFIED Requirements

### Requirement: Facade query for candidate memories
The `GeoMemory` public facade SHALL expose a strictly-typed method `list_candidate_memories` to query candidate memories by lifecycle state and temporal criteria, returning a list of `CandidateMemory` Pydantic models with all type hints (`Sequence`, `str`, `list`) fully defined and importable for runtime inspection and static type checkers.

#### Scenario: Query verified candidates
- **WHEN** an external library calls `ws.list_candidate_memories(states=["verified", "supported"])`
- **THEN** matching `CandidateMemory` instances are returned without requiring raw database access

#### Scenario: Type inspection without error
- **WHEN** `typing.get_type_hints` or static type checkers (`mypy`, `ruff`) inspect `Workspace.list_candidate_memories`
- **THEN** type evaluation succeeds without `NameError` or undefined symbol diagnostics
