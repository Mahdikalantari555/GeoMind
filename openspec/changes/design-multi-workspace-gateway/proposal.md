# Proposal: design-multi-workspace-gateway (DESIGN ONLY — deferred)

## Why

ARCHITECTURE.md risk #6: the gateway holds exactly **one active
workspace** (`server/src/geofront_api/state.py`); concurrent workspaces
would force a redesign of every router, the SSE bus, and the agent
service. For a single-researcher local product this is acceptable today,
but the first pilot deployment (two projects on one machine, or a shared
lab server) hits it immediately. This change captures the design so the
decision is deliberate, not accidental — **implementation is explicitly
deferred** until a pilot needs it.

## Decision (design sketch)

- Keep the single-writer invariant per workspace; generalize the
  gateway's `AppState` to a `dict[str(workspace_key), WorkspaceSession]`
  where a session bundles `{facade, write_lock, agent_service, data_dir}`.
- Routing: requests target a workspace either by header
  (`X-GeoMind-Workspace: <name>`) or by subpath mount
  (`/api/v1/w/{key}/...`); default key = active workspace for backward
  compatibility (both apps keep working unchanged).
- SSE: one event bus per session; `GET /api/v1/events?workspace=<key>`
  (subscribe-all remains for the console).
- Job manager: jobs tagged with their workspace key; `job.progress`
  events carry the key; cross-workspace job listing stays forbidden.
- SQLite: unchanged — one writer connection **per workspace DB** (each
  workspace already has its own file; no cross-workspace contention).
- Migration path: session registry first, then per-session routing, then
  apps — three shippable stages, each keeping tests green.
- Explicit non-goal: multi-user auth/multi-tenancy (CHARTER: not a SaaS).

## Impact

- **Server:** `state.py`, `main.py` lifespan, event bus, job manager,
  every router's `get_state()` call sites.
- **Apps:** none until stage 3 (backward-compatible default key).
- **Estimated effort:** 2–3 weeks; touches nearly every server module.

## Exit criteria for implementing

Trigger when any of: first pilot needs two concurrent projects on one
gateway; a shared-server deployment is requested; or `apps/studio` gains
a multi-project switcher backed by real sessions.
