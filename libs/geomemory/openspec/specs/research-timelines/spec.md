# research-timelines Specification

## Purpose
Research timelines give a project a chronological, filterable view of candidate decisions, hypotheses, methods, events, and working beliefs without changing the underlying candidate-memory workflow.

## Requirements

### Requirement: Project timeline query
The system SHALL expose `GET /api/v1/research/timeline` with required `project`, optional comma-separated `type`, optional `as_of`, `offset` defaulting to 0, and `limit` defaulting to 50.

#### Scenario: Project filter
- **WHEN** a project label is supplied
- **THEN** only candidates assigned to that project are returned

#### Scenario: Memory-type filter
- **WHEN** one or more memory types are supplied
- **THEN** only candidates whose memory type is listed are returned

#### Scenario: As-of filter
- **WHEN** an as-of timestamp is supplied
- **THEN** candidates observed after that timestamp are excluded

### Requirement: Timeline ordering and pagination
Timeline results SHALL be ordered by effective `observed_at` descending and SHALL return both the page of candidate memories and the total number of matching candidates.

#### Scenario: Newest-first order
- **WHEN** a project contains candidates observed on different dates
- **THEN** the newest observed candidate appears first

#### Scenario: Page boundary
- **WHEN** a request uses a nonzero offset or a limit smaller than the result count
- **THEN** the response returns only the requested page and reports the full total
