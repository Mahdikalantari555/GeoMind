# gateway-job-progress

## Purpose

Define server-side progress reporting for long operations, consumed by
GeoMind Studio (and any gateway client). One mechanism feeds every progress
bar: REST for catch-up, SSE for live updates.

## ADDED Requirements

### Requirement: Jobs expose progress
Every long-running job SHALL expose progress fields in `GET /api/v1/jobs/{id}`:
`stage` (short machine-readable stage name), `percent` (0–100 integer or
`null` when indeterminate), and `detail` (short human-readable string).
Existing job states (running/succeeded/failed) are unchanged.

#### Scenario: Job with progress
- **WHEN** a running download job is polled via `GET /jobs/{id}`
- **THEN** the response includes stage, percent, and detail

### Requirement: SSE progress events
The existing SSE stream (`GET /api/v1/events`) SHALL emit a
`job.progress` event on each progress update, carrying job id, stage,
percent, and detail. Events SHALL be emitted at a bounded rate (no more than
~4 updates/second per job) to keep the stream cheap.

#### Scenario: Live progress stream
- **WHEN** a job progresses from stage A to stage B
- **THEN** subscribed clients receive `job.progress` events reflecting both
  transitions in order

### Requirement: All long jobs report progress
Long operations — downloads, ingest/index, training — SHALL report progress
through this mechanism. A capability without meaningful progress SHALL report
an indeterminate stage rather than nothing.

#### Scenario: Ingest progress
- **WHEN** an ingest job indexes many segments
- **THEN** percent reflects processed/total segments with a stage name

### Requirement: Reconnect catch-up
A client that reconnects SHALL recover the true current job state from
`GET /jobs/{id}` without replaying missed SSE events. Progress SHALL be
idempotent per job (no gaps that break percentage rendering).

#### Scenario: Reload mid-job
- **WHEN** the client reloads while a job runs
- **THEN** the UI shows the correct current stage/percent fetched from REST,
  then continues from SSE events
