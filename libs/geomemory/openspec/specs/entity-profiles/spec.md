# entity-profiles Specification

## Purpose
Entity profiles turn manually maintained aliases and existing entity relations into a single view of current beliefs, revision history, and neighboring research entities.

## Requirements

### Requirement: Seeded alias entity matching
The system SHALL match candidate content against a configurable seeded alias index using case-insensitive substring matching. When aliases collide, all matching entities SHALL remain linked.

#### Scenario: Alias match
- **WHEN** candidate content contains a configured alias
- **THEN** the corresponding entity profile includes that candidate

#### Scenario: Alias collision
- **WHEN** one alias is associated with multiple entities
- **THEN** each matching entity profile includes the candidate

### Requirement: Entity profile payload
An entity profile SHALL return the entity name and kind, active candidate beliefs, all superseded history for those beliefs, and related entity names. An unknown entity SHALL produce an empty profile at the service boundary.

#### Scenario: Current and historical beliefs
- **WHEN** an entity has an active belief and a superseded revision
- **THEN** the active belief appears in current beliefs and the old revision appears in history

#### Scenario: Related entities
- **WHEN** two entities are connected by a relation or co-mentioned in a candidate memory
- **THEN** each entity profile lists the other as related

### Requirement: Entity profile gateway response
The gateway SHALL expose `GET /api/v1/memory/entities/{entity_name}` and SHALL return the profile payload for a known entity.

#### Scenario: Known entity response
- **WHEN** the gateway receives a request for a known entity
- **THEN** it returns HTTP 200 with current beliefs, history, and related entities

#### Scenario: Unknown entity response
- **WHEN** the gateway receives a request for an unknown entity
- **THEN** it returns HTTP 404 with an entity-not-found error
