# studio-acquire

## Purpose

Define the Acquire page: scene search for the current ROI and download jobs
with live progress. This is the "money demo" — draw a box, get satellite
data, watch it arrive.

## ADDED Requirements

### Requirement: Scene search for current ROI
The Acquire page SHALL search scene availability for the current ROI by
sensor (Landsat 8/9, Sentinel-2) and date range. Results SHALL list scene id,
acquisition date, cloud cover, and geometry preview, and SHALL mark scenes
already present in the workspace.

#### Scenario: Search with ROI and filters
- **WHEN** the user picks a sensor and date range for the current ROI
- **THEN** matching scenes are listed with metadata and "already owned" marks

#### Scenario: No ROI selected
- **WHEN** no ROI is selected
- **THEN** the page shows an instructional empty state with a "draw an ROI"
  action that focuses the map

### Requirement: Download jobs with live progress
Starting a download SHALL create a gateway job. The page SHALL render live
progress per job: stage name, percent, and detail, driven by SSE
`job.progress` events with `GET /jobs/{id}` as the catch-up path on
reconnect.

#### Scenario: Progress while downloading
- **WHEN** a download job runs
- **THEN** the UI shows the current stage and percent updating live, and
  recovers the correct state after a page reload

#### Scenario: Job fails
- **WHEN** a download job fails partway
- **THEN** the failed scene shows the error and a "retry" action; completed
  scenes are unaffected (per-scene resumability)

### Requirement: Queue view and cancel
Multiple downloads SHALL render as a queue with state per scene
(queued/running/done/failed). Running jobs SHALL be cancellable; cancellation
SHALL stop the job server-side and mark the scene cancellable-resumable.

#### Scenario: Cancel a running download
- **WHEN** the user cancels a running job
- **THEN** the job stops server-side and the queue shows it as cancelled
  with a restart action

### Requirement: Auto-ingest into workspace
A finished download SHALL automatically register the scene in the workspace
(ingest job) so it becomes searchable and mappable. The page SHALL show the
chain (download → ingest → index) as one continuous progress story.

#### Scenario: Chain completes
- **WHEN** the download and ingest chain finishes
- **THEN** the scene appears in Resources and as a map layer with all chain
  stages marked done

### Requirement: Fetcher-absent empty state
When the scene fetcher backend (`data_engine` `add-scene-fetcher`) is not
available, the Acquire page SHALL show a designed empty state explaining the
missing capability and its install step — never a crash or blank page.

#### Scenario: Fetcher missing
- **WHEN** the gateway reports the fetcher unavailable
- **THEN** the page shows the explanation and install guidance
