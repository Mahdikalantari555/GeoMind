# Proposal: add-studio-knowledge-agent

## Why

GeoMind Studio's shell, map, and Acquire flow exist after
`add-svelte-studio-app`, but the knowledge surfaces — resources, cited Q&A,
and the agent — do not. The vision's promises 2 and 3 ("Ask → Cite",
"agent parity") require them. The old app's failure mode ("model didn't
respond") is addressed head-on: the agent surface must degrade to
retrieval-only and never strand the user.

## What Changes

- **Resources page**: drag-drop ingest (PDFs, GeoTIFFs, GeoJSON), ingest and
  indexing progress from `job.progress` SSE, collection management, index
  stats (no raw JSON).
- **Ask page**: search + grounded QA; citation chips open the exact segment
  in a split view; per-claim grounding display; abstention as a designed
  first-class state with sources.
- **Agent rail**: streaming chat in the right rail; plan display; each tool
  call as an inspectable card (args, artifacts, latency, status); playbook
  replay; invalid `[S#]` citations stripped and flagged, never rendered.
- **Agent parity tools**: gateway-facing tools `roi_create` and
  `data_download` so the agent can do everything the Map/Acquire pages can —
  same endpoints, same audit trail.
- Agent works in retrieval-only mode when no LLM is configured (explicit
  abstention UI, no hang).

## Capabilities

### New Capabilities
- `studio-resources` — ingest UX, progress, collections, index stats.
- `studio-ask` — cited QA with claim grounding and abstention.
- `studio-agent-rail` — streaming agent surface with tool trace and
  playbooks.
- `studio-agent-parity` — agent tools for ROI and download operations
  (gateway-side wiring to existing job endpoints).

## Impact

- **Server:** two new tool wrappers (`roi_create`, `data_download`) over
  existing routes; no new routes. OpenAPI regenerated.
- **Libs:** none (uses existing geoagent/geomemory facades).
- **Studio:** three new pages/rails; SSE client infrastructure reused from
  the first change.

## Dependencies

- Builds on `add-svelte-studio-app` (shell, SSE, job progress).
- `add-scene-fetcher` must land for `data_download` to be fully functional;
  until then the tool surfaces the same designed unavailability state.
