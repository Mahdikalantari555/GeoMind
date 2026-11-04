# Findings: Research Assistant & Agent Rail UX

## Root Causes Identified
1. Currently implemented as a `fixed bottom-6 right-6 w-96` floating popover card. It blocks the map viewport, cannot be resized, has no conversation history, and lacks quick-prompt suggestions.
2. The visual target mockups (`geomind-design/`) and `VISION.md` specify a 3-column layout:
   - Left: Layer hierarchy & tools
   - Center: Interactive MapLibre canvas
   - Right: Docked Agent Rail (collapsible/expandable, 320px-450px wide) with tabs (Chat / Prompt Inspector / Grounding Sources).
3. Grounding citations are static text chips. Users cannot click them to highlight the corresponding raster layer or zoom to the cited ROI polygon.

## Solution Architecture
1. **Docked Agent Rail Component (`AgentRail.svelte`)**:
   - Replaces floating `GuidedQuestionRail.svelte`.
   - Collapsible dock alongside `MapView.svelte`.
   - Header with token counter, model badge (Retrieval-Only vs Generative), and clear/minimize buttons.
   - Conversation stream with user query, assistant markdown response, and interactive citation badges.
   - Input bar with multi-line textarea, pre-configured research prompts, and stop/submit buttons.
2. **Interactive Citation Bridge**:
   - Clicking citation chip triggers `map.fitBounds` or highlights the cited layer in `mapState.layers`.
