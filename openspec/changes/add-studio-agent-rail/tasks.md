# Tasks: add-studio-agent-rail

## 1. Agent Rail Docked Shell
- [x] 1.1 Create `apps/studio/src/lib/components/AgentRail.svelte` as a full-height right column with collapse/expand toggle.
- [x] 1.2 Add `isAgentRailOpen` state to `studioState` and wire `Ctrl+B` hotkey + TopBar toggle button.
- [x] 1.3 Remove legacy floating `GuidedQuestionRail.svelte`.

## 2. Conversation & Chat Stream Store
- [x] 2.1 Create `apps/studio/src/lib/stores/agent.svelte.ts` to manage chat message history (`role: 'user' | 'assistant'`, text, citations, timestamps).
- [x] 2.2 Wire predefined research prompts ("Peak ETa flux in Sector A", "Irrigation deficit summary", "Hydrologic study context") into the input box.
- [x] 2.3 Add simulated token streaming animation for research replies in retrieval-only mode.

## 3. Interactive Grounding Citation Bridge
- [x] 3.1 Create `CitationBadge.svelte`: clicking citation triggers `mapState.selectLayer(sourceId)` and `mapState.fitToGeometry()`.
- [x] 3.2 Display citation confidence score and source file type badge (Raster vs Document vs Vector).

## 4. Deferred LLM Configuration In-Rail
- [x] 4.1 Embed non-blocking LLM provider setup card directly in the chat feed after the first cited answer.
- [x] 4.2 Support dismissible / minimize state for the LLM setup card.

## 5. Verification & Tests
- [x] 5.1 Write unit tests in `agent.test.ts` for message history, prompt injection, and citation dispatch.
- [x] 5.2 Validate quality gates: `pnpm check && pnpm lint && pnpm test`.
