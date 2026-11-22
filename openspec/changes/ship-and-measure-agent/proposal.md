# Proposal: ship-and-measure-agent

> Direction + delivery change. Root `openspec/changes/`. Merges the remaining
> "make it a real product" items: the turnkey demo, the benchmark numbers and
> the two roadmap capabilities that are one bridge away from existing infra.

## Why

The audit's final findings are not bugs but unmet promises that block a
credible presentation:

- `docs/CHARTER.md:81` says the "Now" phase publishes retrieval-parity,
  abstention and 100 % citation numbers; `tasks/todo.md:14` says the end
  criterion is published numbers; `openspec/changes/publish-agent-baseline/`
  is still only a proposal and `docs/benchmarks/` does not exist. The spine's
  identity is a claim, not a measurement.
- `tasks/todo.md:38` says live agent chat in Studio is still a scripted
  placeholder — users see fixture replies where "agent parity" is promised.
- `tasks/todo.md:20` describes vision search on the map as unbuilt even though
  `POST /images/search` exists (`SPEC_SERVER.md:95`) and the OlmoEarth/ONNX
  embeddings are available; a "find tiles similar to this parcel" view is one
  tiles-to-embedding bridge away.
- The only turnkey Docker deliverable ships the **frozen** `apps/web` admin
  console (`docker-compose.yml:23`, `README.md:65`), not Studio — so the
  "60-second demo" shows the deprecated reference app.

These are owned as one delivery tranche so the release story, the measurements
that justify it and the two differentiating views land together.

## What Changes

- Add a `studio` service to `docker-compose.yml` (multi-stage Vite single-file
  build → nginx with the same `/api` proxy), make it the default demo target,
  and move `web` behind a `reference` profile. Update README quickstart to
  point at Studio. Verify the single-worker gateway/SQLite invariant still holds.
- Publish the benchmark baseline: freeze corpus slice/seeds/metric definitions,
  run the existing benchmark tooling, write `docs/benchmarks/report.md` with a
  retrieval-parity ablation table (hybrid vs text-only vs vector-only,
  nDCG@10/MRR), abstention precision/recall and machine-checked citation
  correctness (target 100 %), then wire the regression hook before archiving
  `publish-agent-baseline`. Add a results table to README.
- Replace the scripted AgentRail replies with the real streamed `/agent/chat`
  SSE flow: define the session/conversation-ID handoff and tool-card rendering
  from the existing SSE event names, implement behind a flag, retire the
  scripted path, and add e2e coverage. (The correctness fixes for that rail are
  in `studio-product-completion`.)
- Spike vision search on the map: implement the tiles-to-embedding bridge
  against an existing workspace, validate retrieval quality on `sample/`, and
  define the Studio interaction (tile vs scene granularity is an open question
  in `tasks/todo.md`). Produce a decision record; do not commit to full UI work
  until the spike reports quality.
- Spike the specified-but-absent agent exposure surface: the `learning-loop`
  spec names `geo_record_feedback`, `geo_review_queue`, `geo_review`,
  `geo_export_dataset` and `geo_export_runs` but none exist in `geoagent/src`;
  the `mcp-interface` spec names a `geoagent mcp` command that `cli.py` does not
  define. Decide which of these are in the shipped spine, thin-wrap the
  existing facades for the learning-loop tools, and defer MCP transport until
  confirmed. Also cap the tool manifest per the `tool-registry` spec.

## Capabilities

### Modified Capabilities
- `docker-deployment` — Studio is the default single-box front; web is optional.
- `benchmark-corpus` / `regression-tracking` — published, repeatable numbers.
- `studio-agent-rail` — live gateway chat replaces scripted replies.

### New Capabilities (spike only)
- `vision-search-on-map` — prototype tiles-to-embedding bridge + interaction
  decision record.

## Impact

- **Root:** `docker-compose.yml`, `README.md`, `docs/benchmarks/` (new),
  `docs/CHARTER.md` status lines, `tasks/todo.md`.
- **Studio:** AgentRail live path behind a flag; new vision view only if the
  spike passes its quality gate.
- **CI:** one benchmark/regression job; Docker smoke test of the Studio service.

## Dependencies

- `product-hardening-and-trust` (auth/bind defaults) and
  `studio-product-completion` (rail correctness, token transport) land first.
- Builds on the open `publish-agent-baseline` and `add-studio-knowledge-agent`
  changes — this change completes and archives them, it does not duplicate them.

## Out of Scope

- Changing the benchmark targets in `publish-agent-baseline` without owner
  confirmation.
- Shipping the vision view if the spike's retrieval quality is not credible —
  report and stop.
- Multi-user/SaaS deployment.

## Findings covered

F-094, F-095, F-096, F-097, F-098, DIR-01…04 (cross-cutting direction),
DOC-01 (benchmark unmet).
