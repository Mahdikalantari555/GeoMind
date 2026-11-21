# app-presentation

## Purpose

Define the presentation and information-architecture layer of the GeoMind web
app so that the already-implemented capabilities are discoverable and a new
end user reaches a cited answer within five minutes. Covers home dashboard,
hub-based navigation, simple/advanced mode, empty states, command palette, and
consistent page headers. No gateway or data-model changes.

## ADDED Requirements

### Requirement: Home dashboard
The app SHALL render a Home dashboard as the landing route (`/`) that provides:
a hero call-to-action to ask a question, quick actions (Ask, Ingest, Map), a
"Try in 5 minutes" guided path using bundled sample data, recent activity, and
workspace health cards (collections, assets, segments, storage). It SHALL NOT
display raw JSON stats.

#### Scenario: Workspace open
- **WHEN** a workspace is open
- **THEN** the Home dashboard shows health cards and quick actions
- **AND** no raw JSON is rendered

#### Scenario: No workspace
- **WHEN** no workspace is open
- **THEN** the Home dashboard shows the setup affordance and the sample-data
  guided path

### Requirement: Three-hub navigation
The sidebar SHALL group routes into three hubs — Knowledge, Geo, Agent — plus a
collapsible Workspace section. Each hub SHALL be collapsible and SHALL persist
its collapsed state.

#### Scenario: Default view
- **WHEN** the app loads
- **THEN** all three hubs are visible and the Workspace section is collapsed

### Requirement: Simple and Advanced modes
The app SHALL support a Simple mode (default) and an Advanced mode toggle. In
Simple mode only the core pages (Home, Ask, Search, Ingest, Map) are visible
in navigation; Advanced mode exposes all pages. The toggle SHALL be in the
header and persist across sessions.

#### Scenario: Simple mode navigation
- **WHEN** Simple mode is active
- **THEN** only Home, Ask, Search, Ingest, and Map appear in navigation

#### Scenario: Toggle persists
- **WHEN** the user switches to Advanced mode and reloads
- **THEN** Advanced mode remains active

### Requirement: Empty states
Every page SHALL render a designed empty state with a title, explanation, and a
primary call-to-action when it has no data (no workspace, no assets, no
collections, no farms, no conversations). Empty states SHALL never be blank
screens.

#### Scenario: No assets
- **WHEN** the Assets page has no assets
- **THEN** an empty state with an "Ingest your first document" CTA is shown

### Requirement: Command palette
The app SHALL provide a command palette triggered by Ctrl/Cmd+K that lists all
pages (and recent items in Advanced mode) and navigates on selection. It SHALL
be keyboard-accessible and dismissible with Escape.

#### Scenario: Open palette
- **WHEN** the user presses Ctrl/Cmd+K
- **THEN** the command palette opens and focuses its input

#### Scenario: Navigate
- **WHEN** the user selects a page in the palette
- **THEN** the app navigates to that page and closes the palette

### Requirement: Consistent page headers
Every page SHALL use a shared PageHeader component with title, optional
subtitle, and optional primary action, ensuring consistent vertical rhythm.

#### Scenario: Header present
- **WHEN** any page renders
- **THEN** a PageHeader with at least a title is displayed

### Requirement: Onboarding guided path
The Home dashboard SHALL include a "Try in 5 minutes" three-step guided path:
(1) open or create a sample workspace, (2) ask a question, (3) view the cited
answer. Each step SHALL link to the relevant page.

#### Scenario: Steps link
- **WHEN** the guided path renders
- **THEN** each step is a link to its target page