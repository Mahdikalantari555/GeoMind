## MODIFIED Requirements

### Requirement: Candidate memory store
Every feedback submission SHALL be stored as an addressable candidate memory with fields `{id, content, memory_type, source_feedback_ids, confidence_score, state, author, audit_trail, created_at, updated_at, observed_at, superseded_by, project}` and linked provenance when applicable. `observed_at` is nullable and represents when the belief was true; `superseded_by` links a replaced belief to its replacement; `project` scopes the belief to a research project.

#### Scenario: Correction creates candidate
- **WHEN** a user edits "Salinity stress primarily affects NDVI." to "Salinity stress often affects NDVI, but thermal indicators may respond earlier."
- **THEN** a candidate memory is created with `memory_type=correction`, `state=proposed`, and the existing review metadata, while the authoritative knowledge base remains unchanged

#### Scenario: Annotation creates fact
- **WHEN** a user adds "Under arid conditions, canopy temperature often separates water stress from salinity more effectively than spectral indices."
- **THEN** it is stored as `memory_type=annotation`, `state=proposed`, with confidence initialized low

#### Scenario: Temporal metadata is preserved
- **WHEN** a candidate is created with an observation time and project label
- **THEN** those values remain available on reads and can be used by temporal and timeline queries

## ADDED Requirements

### Requirement: Entity-linked candidate views
The system SHALL expose entity profiles that return active candidate beliefs, the full supersession history, and related entity names for a requested entity. Entity matching SHALL use the configured seeded alias index without automatic entity extraction.

#### Scenario: Known entity profile
- **WHEN** a requested entity matches a seeded alias in candidate content
- **THEN** the profile includes the matching active beliefs and their revision history

#### Scenario: Unknown entity profile
- **WHEN** no candidate or relation matches the requested entity
- **THEN** the profile contains no beliefs, no history, and no related entities

### Requirement: Project research timelines
The system SHALL expose a project-scoped timeline of candidate memories filtered by optional memory types and an optional as-of time, ordered from newest observation to oldest and paginated.

#### Scenario: Filtered timeline
- **WHEN** a project and memory types are supplied
- **THEN** only matching candidates are returned in descending effective observation order

#### Scenario: Timeline pagination
- **WHEN** a timeline request supplies `offset` and `limit`
- **THEN** the response contains the requested page and the total matching count

### Requirement: Superseded candidate exclusion
Candidate search SHALL exclude rows linked by `superseded_by` by default and SHALL include them only when the caller explicitly opts in.

#### Scenario: Default search excludes superseded candidates
- **WHEN** a query matches only a superseded candidate
- **THEN** the candidate is absent from search results

#### Scenario: Explicit superseded search
- **WHEN** the caller enables `include_superseded`
- **THEN** matching superseded candidates are eligible for results
