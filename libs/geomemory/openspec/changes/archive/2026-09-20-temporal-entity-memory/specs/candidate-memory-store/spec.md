## Purpose

Candidate memories retain temporal observation, supersession links, and project labels so researchers can inspect belief history without changing the existing review workflow.

## ADDED Requirements

### Requirement: Temporal candidate memory fields
Candidate memories SHALL persist an optional `observed_at` ISO timestamp, an optional `superseded_by` reference to the candidate that replaced them, and an optional `project` label alongside the existing content, type, confidence, state, author, audit trail, source feedback, and timestamps.

#### Scenario: Temporal metadata round trip
- **WHEN** a candidate memory is created with `observed_at`, `superseded_by`, and `project`
- **THEN** all three values are returned unchanged when the candidate is read back

#### Scenario: Legacy candidate remains readable
- **WHEN** an existing candidate has no `observed_at`
- **THEN** it remains readable and its effective observation time is its creation time

### Requirement: As-of candidate read
The candidate store SHALL return the latest revision in a supersession chain whose effective `observed_at` is not later than the requested time, and SHALL return no revision when none qualifies.

#### Scenario: Select historical revision
- **WHEN** a candidate chain contains observations at two different times and an as-of time between them
- **THEN** the earlier revision is returned

#### Scenario: Select current revision
- **WHEN** the requested as-of time is later than every revision in a candidate chain
- **THEN** the newest revision is returned
