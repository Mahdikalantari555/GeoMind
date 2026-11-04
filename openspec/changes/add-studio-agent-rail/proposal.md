# Proposal: add-studio-agent-rail

## Intent
Replace the floating popover card with a docked 3-column Agent Rail interface matching the target instrument design (`geomind-design/`). Provide multi-turn research conversation, prompt suggestion chips, and interactive citation-to-map linking.

## Scope
1. Implement `AgentRail.svelte` as a full-height collapsible right drawer (width 380px) in `apps/studio`.
2. Support multi-turn chat message streaming, markdown code/list rendering, and prompt suggestion tags ("Peak ETa flux", "Parcels at risk", "Water consumption summary").
3. Make citation chips interactive: clicking a citation highlights the cited layer on the map and pans/zooms to the relevant geometry.
4. Integrate deferred LLM configuration directly inside the rail without disrupting ongoing dialogue.
