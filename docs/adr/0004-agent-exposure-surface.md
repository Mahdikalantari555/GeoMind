# ADR 0004 — Learning-loop tools ship; MCP transport is deferred

- Status: Accepted (learning-loop implemented; MCP deferred)
- Date: 2026-11-24
- Scope: `libs/geoagent/src/geoagent/tools/learning_loop_tools.py`, `registry.py`
- Finding: F-098

## Context

The `learning-loop` spec names five tools (`geo_record_feedback`,
`geo_review_queue`, `geo_review`, `geo_export_dataset`, `geo_export_runs`) and
the `mcp-interface` spec names a `geoagent mcp` stdio server. None had an
implementation. `tool-registry` also requires a token-bounded tool manifest with
on-demand family expansion.

## Decision

1. **Ship all five learning-loop tools** as thin wrappers in `geoagent`, using
   only GeoMemory's public facade (`record_feedback`, `get_review_queue`,
   `review_example`, `export_dataset`) and the agent's own `tool_run` audit
   table. No `libs/geomemory` or `libs/geolearn` change was needed.
   - `geo_record_feedback(rating?, comment, target_refs[])` maps to one immutable
     `FeedbackEvent` per target ref; `rating`/`comment` live in `payload`, the
     full ref list in `metadata` (the facade model has no dedicated fields).
   - Both exports return `ArtifactRef` so `Registry.call` computes SHA-256.
   - `geo_export_runs` reads `tool_run` via a new `Store.list_tool_runs`;
     "budgets hit" is derived from `status='budget_refused'`.
2. **Cap the tool manifest** at `DEFAULT_MANIFEST_TOKEN_BUDGET = 1200` tokens in
   `Registry.manifest_lines()` and `openai_tools()`. Overflow families collapse
   to one-line summaries (least-recently-used first, tracked in `Registry._usage`)
   and the built-in `list_tools(family)` tool expands them on demand.
3. **Defer `geoagent mcp` transport.** The single execution path already exists
   (`Registry.call` → validation → sandbox → audit), so a stdio MCP `tools/call`
   could reuse it, but the spec places this at P5, there is no MCP SDK dependency
   or `mcp.expose[]` config, and the change's own task says to defer transport
   until confirmed. Implementing it now would add an unrequested network-facing
   surface to a local-first tool.

## Consequences

- The feedback → review → export plumbing that the spine depends on is now
  callable by the agent and by playbooks.
- Tool prompts are bounded; adding many custom tools cannot silently blow the
  context budget.
- MCP exposure remains a deliberate follow-up requiring owner confirmation.
