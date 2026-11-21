# studio-shell

## Purpose

Define the GeoMind Studio app frame: routing, layout, theming, and the
no-dead-ends contract that guarantees the user is never stranded. This is the
capability the old React app most violated: unusable states with no way out.

## ADDED Requirements

### Requirement: Map-first layout
The app SHALL render a map-first layout: a persistent layer panel (left), the
map canvas as the home route, and a collapsible agent rail (right, dormant
until the `add-studio-knowledge-agent` change). A top bar SHALL hold the
workspace switcher, command palette trigger (Ctrl/Cmd+K), and health status.

#### Scenario: App load with workspace
- **WHEN** a workspace is open
- **THEN** the map canvas fills the viewport with the layer panel and top bar
  visible

### Requirement: No dead ends
Every user-facing failure SHALL have a designed next action. There SHALL be
no raw error dumps, no silent failures, and no page that renders empty
without instruction. Specifically:
- LLM unavailable → retrieval-only answers continue; a config affordance is
  offered (deferred until after the first answer).
- Gateway unreachable → a reconnect state with a retry action.
- No basemap tiles → the map renders with a bundled offline fallback style.
- Empty data → an instructional empty state naming the next action.

#### Scenario: LLM unconfigured
- **WHEN** no LLM backend is configured and the user asks a question
- **THEN** the app shows retrieval snippets with sources and a clear
  "configure an LLM" affordance, and does not crash or hang

#### Scenario: Gateway unreachable
- **WHEN** the gateway is unreachable
- **THEN** the app shows a reconnect state with a retry action and the
  workspace name

### Requirement: Health surface
The app SHALL provide a health/doctor view diagnosing: workspace open state,
index status, LLM backend reachability (probe), data-source reachability, and
storage. Each check SHALL show pass/fail and the fix action when failed.

#### Scenario: Sick workspace
- **WHEN** the index is empty but assets exist
- **THEN** the health view shows the failing check with a "reindex" action

### Requirement: Instrument theme
The app SHALL implement the scientific-instrument visual language using
shadcn-svelte components + Tailwind: dark-first palette, monospace numerics
for coordinates/statistics, consistent page headers, and skeleton loading
states on every async surface.

#### Scenario: Coordinates render
- **WHEN** a coordinate or numeric stat is displayed
- **THEN** it uses the monospace numeric style

### Requirement: Code quality gates
The app code SHALL pass: `svelte-check` with strict settings, ESLint, and
Prettier formatting. Every capability's core logic SHALL be covered by Vitest
unit tests. End-to-end tests are deferred to a later change.

#### Scenario: Quality gate run
- **WHEN** `pnpm check && pnpm lint && pnpm test` runs in `apps/studio`
- **THEN** all three pass with zero errors
