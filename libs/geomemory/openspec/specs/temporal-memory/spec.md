# temporal-memory Specification

## Purpose
Temporal memory lets researchers reconstruct what a candidate belief said at a point in time while keeping the time the system learned it separate from the time the belief was observed.

## Requirements

### Requirement: Effective observation time
A candidate without an explicit `observed_at` SHALL use its `created_at` only when read or queried; the stored `observed_at` value SHALL remain null until a caller explicitly supplies one.

#### Scenario: Read-time default
- **WHEN** a legacy candidate has no stored observation time
- **THEN** temporal reads treat its creation time as the effective observation time without rewriting the row

### Requirement: Point-in-time candidate query
The system SHALL support querying a candidate supersession chain by an as-of timestamp and SHALL select the latest revision whose effective observation time is at or before that timestamp.

#### Scenario: Historical belief lookup
- **WHEN** a researcher requests a candidate as of March 2025
- **THEN** the returned content is the revision observed at or before March 2025, not a later revision

#### Scenario: No qualifying revision
- **WHEN** every revision in the chain was observed after the requested timestamp
- **THEN** the query returns no candidate
