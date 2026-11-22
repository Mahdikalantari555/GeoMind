# retrieval-parity — Spec Delta

## MODIFIED Requirements

### Requirement: Deleted assets are not retrievable

Every search path — FTS, dense and image — SHALL exclude segments belonging to
assets with a non-null `deleted_at`. Soft delete SHALL also remove affected
segment ids from persisted vector/image indexes or filter them by revision id
at retrieval time. A deleted asset's text SHALL NOT appear in results or
citations.

#### Scenario: deleted document is not searchable
- **WHEN** an asset with a unique token is soft-deleted and the same token is searched
- **THEN** no hit references that asset

### Requirement: Atomic migrations

Each migration SHALL be a single atomic unit: either all DDL and the version-row
insert commit, or neither. `executescript`'s implicit commit SHALL NOT split a
migration into two transactions. A failure-injection test SHALL assert no DDL
and no version row survive.

### Requirement: Relevance threshold and provenance

`min_score` SHALL be compared against a normalized relevance value in `[0,1]`
(document the scale), not an RRF rank score. Image and candidate citations
SHALL carry a target type so they can be traced to asset revisions or be
explicitly marked non-persisted; the traceable chain SHALL hold for every
returned citation. Temporal filters SHALL parse timestamps to aware datetimes
before comparison. Searches SHALL validate that the embedder's space matches
the index space being queried.
