# Specification: Design System & Instrument Shell

## Requirements

### Requirement 1: Emerald Scientific Design Tokens
The application MUST implement an emerald/teal precision instrument theme across light and dark modes.

#### Scenario: Visual token verification
- **Given** the app renders in light or dark mode
- **When** checking CSS custom properties `--gf-accent`, `--gf-bg`, `--gf-panel`, and `--gf-border`
- **Then** `--gf-accent` resolves to an emerald/teal hue (approx `#00876c` in light mode, `#10b981` in dark mode)
- **And** all metrics and coordinates use `font-mono tabular-nums`.

### Requirement 2: Navigation Rail & Top Bar
The application shell MUST feature an icon-based navigation rail and a persistent header with global search trigger.

#### Scenario: Navigating via icon rail
- **Given** the user views the main window
- **When** clicking an icon in the left/right rail
- **Then** the active route changes with visual highlight on the selected icon
- **And** the top header displays the active workspace name, global search bar, and system status indicator.

### Requirement 3: Workspace Setup Split Modal (`KwzrE.jpg`)
The application MUST provide a split-pane workspace switcher modal.

#### Scenario: Opening workspace modal
- **Given** the user clicks the workspace indicator or shortcut
- **When** the modal opens
- **Then** the left pane lists known workspaces with search, last-opened sort, and active badge
- **And** the right pane displays workspace creation controls with a "Load Demo Workspace" 1-click action.

### Requirement 4: Metric Cards with Sparklines (`lQSVu.jpg`)
The home dashboard MUST render system telemetry cards with sparklines.

#### Scenario: Dashboard telemetry rendering
- **Given** a workspace is open
- **When** navigating to the overview dashboard
- **Then** 4 telemetry cards render (Indexed Assets, Stored Vectors, Active Playbooks, Health)
- **And** each card displays the current count, delta indicator, and an inline SVG sparkline curve.
