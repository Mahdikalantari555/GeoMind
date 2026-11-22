# studio-agent-rail — Spec Delta

## MODIFIED Requirements

### Requirement: Streaming citations are preserved

The rail SHALL NOT strip `[n]` citation markers from a stream whose citation
list has not arrived. Cleanup, if any, SHALL run once after the terminal event
against the actual citation set; a healthy answer SHALL NOT be labelled as
having stripped invalid citations.

#### Scenario: healthy streamed answer keeps citations
- **WHEN** the stream emits `[1]` and the terminal event carries a valid citation
- **THEN** the rendered answer contains `[1]` with no invalid-citation warning

### Requirement: Cancellable streaming and branded requests

`streamAgentChat` SHALL accept an `AbortSignal`. Unmount, reset or a new send
SHALL abort the previous stream, cancel the reader and release the lock; no
state update SHALL occur after unmount. Ask and Run-search SHALL use a shared
request-generation guard so only the latest response commits state.

### Requirement: Tool-call identity

Agent tool SSE events SHALL carry call id and arguments; end events SHALL match
by id (per-name FIFO fallback), so repeated calls to the same tool do not mark
the wrong call complete.
