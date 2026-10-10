# Spec Delta: agent-runtime

## Purpose

Provides reliable autonomous agent execution by synchronizing workspace configurations, tools, context engineering options, and execution serialization.

## ADDED Requirements

### Requirement: Workspace LLM configuration propagation to agent
The agent service SHALL inherit the workspace's configured LLM provider settings, including API base URL, model identifier, and API key environment variable name.

#### Scenario: Agent initialized with custom gateway
- **WHEN** a workspace configured with a custom LLM base URL and model is active
- **THEN** the agent service constructs its backend using those settings rather than defaulting to public OpenAI endpoints

### Requirement: Non-empty agent response fallback and error propagation
`AgentCore.chat` SHALL log raw LLM responses and SHALL NOT emit an empty text response. If the model returns no content and no tool calls, it SHALL return a descriptive fallback message. The chat stream SHALL emit an SSE `error` event whenever the LLM backend raises an exception.

#### Scenario: LLM returns empty content
- **WHEN** the completions API returns an empty content string with no tool calls
- **THEN** the agent emits a fallback notice such as "The model returned an empty response" instead of an empty message bubble

#### Scenario: LLM raises backend exception
- **WHEN** the completions API encounters a connection error or authentication failure
- **THEN** the SSE stream emits an `error` event with error details and terminates cleanly

### Requirement: Agent context scoping for collections and assets
The agent chat endpoint and agent execution loop SHALL accept an optional `context_scope` (collection IDs and asset IDs) and inject summarized metadata or excerpts of the selected context into the agent's prompt.

#### Scenario: Scoped agent conversation
- **WHEN** a user initiates agent chat with specific collections or assets selected in the UI
- **THEN** the agent receives the scoped context in its instructions and focuses analysis on the selected assets

### Requirement: Resilient GIS tool geometry handling
Advisor and GIS tools SHALL handle empty or null geometries gracefully without throwing exceptions during bounding box calculation.

#### Scenario: GeoJSON with null geometry parsed
- **WHEN** a farm report tool processes a feature collection containing empty or null geometries
- **THEN** the tool skips bounding box calculations for empty geometries and does not raise an unhandled exception

### Requirement: Agent tool memory access serialization
Agent memory tools that read or write workspace data SHALL operate safely within the platform's single-writer concurrency model, reusing the active workspace instance rather than opening unmanaged duplicate SQLite connections.

#### Scenario: Agent ingests document via tool
- **WHEN** the agent calls the `geo_ingest` tool during a conversation
- **THEN** the operation executes without opening unmanaged duplicate database handles and respects workspace write serialization
