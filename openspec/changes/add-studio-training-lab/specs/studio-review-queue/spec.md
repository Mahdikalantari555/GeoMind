# studio-review-queue

## Purpose

Define the review queue: the human gate where feedback becomes training
data. Every decision is auditable and traceable to the artifact that
produced it (SHA-256 provenance chain).

## ADDED Requirements

### Requirement: Pending review list
The page SHALL list pending feedback items (rejected/accepted candidate
answers, correction events) with: source context (the answer/question that
generated them), the evidence segments, and proposed correction. Items SHALL
link to their provenance chain (answer → citation → segment → asset).

#### Scenario: Review an item
- **WHEN** the user opens a pending item
- **THEN** the source context, evidence, and proposed correction render with
  a working provenance link

### Requirement: Accept / reject with bulk
Each item SHALL be acceptable or rejectable with an optional note. Bulk
select-and-act SHALL exist. Decisions SHALL be recorded as feedback events
(append-only) with actor and timestamp.

#### Scenario: Bulk accept
- **WHEN** the user selects 5 items and accepts them in bulk
- **THEN** all 5 are recorded as accepted events and leave the queue

### Requirement: Queue impact visibility
The page SHALL show how many accepted items are ready to train on per
`(crop_type, region)` key, and SHALL surface the "Train now" action when a
key crosses a trainable threshold.

#### Scenario: Threshold reached
- **WHEN** a key accumulates ≥30 accepted samples
- **THEN** the page marks the key ready and links to Train now
