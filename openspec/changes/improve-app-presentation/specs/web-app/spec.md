# web-app

## ADDED Requirements

### Requirement: Presentation layer conformance
The web app SHALL conform to the `app-presentation` capability for navigation
grouping (three hubs + collapsible Workspace section), Simple/Advanced mode,
empty states, command palette, consistent page headers, and the Home dashboard.
The flat 19-link sidebar SHALL be replaced by the hub-based navigation.

#### Scenario: Hub navigation
- **WHEN** the app renders the sidebar
- **THEN** routes are grouped into Knowledge, Geo, and Agent hubs
- **AND** the Workspace section is collapsible

#### Scenario: Home dashboard route
- **WHEN** the user navigates to `/`
- **THEN** the Home dashboard (per `app-presentation`) is rendered instead of
  the previous raw-stats Overview