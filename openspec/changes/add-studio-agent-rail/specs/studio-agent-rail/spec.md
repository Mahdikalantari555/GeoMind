# Spec: studio-agent-rail

## Purpose
Deliver a responsive, data-sovereign research assistant interface docked into GeoMind Studio's main viewport.

## Requirements

### Requirement: Docked Right Rail
The Agent Rail SHALL be docked on the right side of the main workspace as a full-height column alongside `MapView`. It SHALL support collapsing/expanding via a toggle button in the header or top bar (`Ctrl+B`).

### Requirement: Multi-Turn Conversation
The assistant SHALL support consecutive user queries. Each response SHALL render formatted text, metadata badges (model provider, response latency, token count), and expandable citation references.

### Requirement: Interactive Grounding Citations
Clicking any citation chip in an answer SHALL:
1. Highlight the cited layer in the sidebar `LayerTree`.
2. Zoom and center the map canvas on the cited parcel or raster boundary.
3. Show a temporary map popup or callout with the citation snippet.

### Requirement: Preset Remote Sensing Prompts
The input area SHALL display quick-click research prompt chips for rapid testing without manual typing (e.g. "Calculate parcel ETa mean", "Check cloud mask", "Cite hydrologic study").
