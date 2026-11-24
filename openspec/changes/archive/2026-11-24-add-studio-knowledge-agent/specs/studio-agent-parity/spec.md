# studio-agent-parity

## Purpose

Define agent/UI parity for workspace operations: the agent gains tools that
call the same gateway endpoints the Map and Acquire pages use, with the same
jobs, progress, and audit trail. Anything a user can do by hand, the agent
can do by tool.

## ADDED Requirements

### Requirement: ROI tool parity
The agent SHALL expose a `roi_create` tool (geometry, name) that saves ROIs
through the same gateway route the Map page uses. Saved ROIs SHALL be
immediately visible in the UI layer tree via SSE — no duplicate ROI store.

#### Scenario: Agent draws an ROI
- **WHEN** the user asks the agent to create an ROI for a described field
- **THEN** the ROI is saved and appears in the layer tree and as the current
  ROI

### Requirement: Download tool parity
The agent SHALL expose a `data_download` tool (ROI, sensor, date range) that
starts the same gateway download job the Acquire page starts. Progress SHALL
flow through `job.progress` SSE and be visible in the Acquire queue and in
the tool card simultaneously.

#### Scenario: Agent downloads for the current ROI
- **WHEN** the agent runs `data_download` for the current ROI
- **THEN** the job appears in the Acquire queue with live progress and in
  the agent's tool card

### Requirement: Audit and citations everywhere
Tool results surfaced in chat SHALL reference the same audit records
(ToolRun) and artifact identities (SHA-256) as UI-initiated operations. The
agent SHALL NOT have private side channels to workspace state.

#### Scenario: Same artifact identity
- **WHEN** a download is initiated by the agent and by the UI separately for
  the same scene
- **THEN** both produce artifacts with identical SHA-256 identities and both
  runs are auditable
