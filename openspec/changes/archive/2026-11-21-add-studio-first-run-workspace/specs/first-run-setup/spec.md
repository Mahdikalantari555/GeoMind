# first-run-setup — Spec Delta

## MODIFIED Requirements

### Requirement: Setup wizard appears at login when no workspace is open

The app SHALL show a setup wizard (modal/overlay) on first run and whenever
the gateway reports the workspace closed, and SHALL NOT let the user dismiss
it without either creating or opening a workspace. **Every application front
MUST conform — including the Studio product front** (`apps/studio`), which
previously deferred this flow to the admin console.

#### Scenario: Fresh load, no workspace

- **WHEN** the app loads and `GET /api/v1/workspace` returns `status: closed`
- **THEN** the setup wizard renders with two tabs: "Create new" and "Open existing"
- **AND** the rest of the app is not reachable until a workspace is open

#### Scenario: Wizard dismissed without action

- **WHEN** the user clicks outside or presses Escape with no workspace open
- **THEN** the wizard stays open (no dismissal); only Create or Open submits close it

## ADDED Requirements

### Requirement: Studio workspace selector reflects gateway state

The Studio top bar SHALL show the active workspace name when a workspace is
open, and an explicit "no workspace" affordance that opens the setup wizard
when closed. The selector SHALL NOT be a dead control.

#### Scenario: Open workspace shown by name

- **WHEN** a workspace is open
- **THEN** the selector displays the workspace name (from `GET /api/v1/workspace`)

#### Scenario: Closed workspace opens the wizard

- **WHEN** the gateway reports the workspace closed
- **THEN** activating the selector opens the setup wizard (or the blocking
  wizard is already shown per the first-run requirement)

### Requirement: Studio tracks workspace changes from events

While the gateway is reachable, Studio SHALL refresh its workspace state when
the `workspace_changed` SSE event is delivered, so create/close performed
through the dialog (or by another client of the same gateway) is reflected
without a manual reload.

#### Scenario: External workspace change

- **WHEN** `workspace_changed` arrives while Studio is connected
- **THEN** Studio re-reads `GET /api/v1/workspace` and updates the selector,
  the wizard visibility, and any workspace-gated affordances

### Requirement: Operations requiring a workspace fail with actionable guidance

When a Studio operation that requires an open workspace fails with
`workspace_not_open` (e.g. saving an ROI), the UI SHALL present an actionable
message directing the user to create or open a workspace — not a raw error
string — and SHALL NOT leave partially-created client state behind (the
optimistic ROI addition is removed, consistent with the existing rollback).

#### Scenario: ROI save with closed workspace

- **WHEN** the user saves an ROI while the workspace is closed
- **THEN** the ROI is not retained in the map ROIs list
- **AND** a toast directs the user to create/open a workspace and offers the
  wizard entry point
