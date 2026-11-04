# studio-agent-rail

## Purpose

Define the agent surface in Studio: streaming chat, visible reasoning, tool
trace, and playbooks. The agent is a peer client of the UI (same gateway
endpoints) and must remain trustworthy when degraded: no LLM means explicit
abstention, never a hang.

## ADDED Requirements

### Requirement: Streaming chat with visible plan
The agent rail SHALL stream responses token-by-token. Before tool execution,
the agent's short step plan SHALL render as a visible, checkable list
tracking each step's status.

#### Scenario: Plan then execute
- **WHEN** the agent receives a multi-step request
- **THEN** the plan renders first and each step updates (pending/running/
  done) as tools execute

### Requirement: Tool trace cards
Every tool call SHALL render as an inspectable card: tool name, arguments
summary, status, latency, and artifact links. Cards SHALL open details
(including error details on failure). Tool runs map to the existing ToolRun
audit records.

#### Scenario: Inspect a failed tool call
- **WHEN** a tool call fails
- **THEN** its card shows the failure status with the error detail from the
  audit record

### Requirement: Citation contract in chat
Answers in chat SHALL carry `[S#]` citations resolvable to `geo_search` hits.
Invalid citation keys SHALL be stripped from the rendered answer and flagged
in answer metadata — never shown to the user as raw markers.

#### Scenario: Invalid citation key
- **WHEN** the model emits a `[S9]` with no matching source
- **THEN** the marker is stripped and the answer metadata notes the strip

### Requirement: Playbook replay
Saved playbooks SHALL be listable and replayable from the rail. Replay SHALL
run the deterministic fast path (no LLM latency) and stream the same tool
trace cards. New playbooks SHALL be savable from a completed agent run.

#### Scenario: Replay a saved playbook
- **WHEN** the user replays a saved playbook
- **THEN** the tool trace runs without LLM calls and completes with the same
  step cards

### Requirement: Degraded agent state
When no LLM is configured, the rail SHALL present retrieval-only behavior
(search via tools, snippets with sources) and an explicit "configure an LLM"
affordance — never a hang, never a silent failure.

#### Scenario: Agent without LLM
- **WHEN** the user asks the agent a question with no LLM configured
- **THEN** the rail responds with retrieval results and the config
  affordance within a bounded time
