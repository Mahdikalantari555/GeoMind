# Comprehensive Research Report: Studio Layer Canvas & Agent Rail UX

**Date:** 2026-11-04  
**Project:** GeoMind Studio (`apps/studio`)  

## Executive Summary
Evaluation of the running GeoMind Studio revealed two core architectural gaps:
1. **Map Layer Invisibility**: `MapView.svelte` only registers a single `rois-source` and never synchronizes raster or vector layers from `mapState.layers` onto the MapLibre GL style tree. Visibility checkboxes in `LayerTree` mutate local store booleans but do not issue `map.setLayoutProperty` calls to the WebGL context.
2. **Clunky Guided Q&A Popover**: The research assistant was rendered as a small floating dialog in the lower-right corner (`GuidedQuestionRail.svelte`). The product charter and visual mockups specify a full-height, docked 3-column instrument layout where the Agent Rail occupies a collapsible right panel with multi-turn prompt history and interactive citation-to-map linking.

---

## 1. Technical Diagnosis

### 1.1 MapLibre GL Layer Synchronization Failure
- In `MapView.svelte`, `onMount` creates only:
  - `map.addSource('rois-source', ...)`
  - `map.addLayer({ id: 'rois-fill', ... })`
  - `map.addLayer({ id: 'rois-line', ... })`
- When `onboardingState.seedSampleWorkspace()` runs, it registers:
  - `layer-eta-sample` (Landsat 9 METRIC ETa raster)
  - `layer-farms-sample` (Sugar-cane field boundaries)
- **Result:** Layers appear in the left sidebar list, but remain 100% invisible on the map canvas. No MapLibre raster/vector sources are created.
- Furthermore, no auto-centering occurs (`fitBounds`), leaving the user at the default zoom level.

### 1.2 Agent Rail Usability Deficit
- Floating widget obscures map navigation controls.
- Single hardcoded question with no textarea input to type custom queries.
- Citations are plain strings with no bidirectional interaction with the map layers.

---

## 2. Proposed OpenSpec Changes

To resolve these cleanly with test coverage and verification, work is structured into two sequential OpenSpec changes:

### Change 1: `add-studio-map-layers`
**Scope:**
- Reactive MapLibre source & layer registry in `MapView.svelte`:
  - Support raster image/tile layers with opacity.
  - Support vector polygon/GeoJSON layers with outline and fill.
  - Sync visibility changes from `mapState.layers` directly to MapLibre layers via `setLayoutProperty`.
- Camera auto-bounds (`fitBounds`) on ROI creation or sample workspace load.
- Interactive layer selection & opacity slider in `LayerTree.svelte`.

### Change 2: `add-studio-agent-rail`
**Scope:**
- Replace floating `GuidedQuestionRail` with docked right-sidebar `AgentRail.svelte`.
- Collapsible dock (width 360px, toggleable via hotkey or top bar).
- Rich conversation interface:
  - Chat stream with formatted markdown output.
  - Multi-line question input with predefined remote-sensing prompt chips ("Estimate ETa", "Check Soil Moisture", "Summarize Hydrology Study").
  - Grounded citation chips that pan/zoom the map canvas to the cited region or toggle the cited layer.
- Retain deferred LLM configuration banner inside the docked rail.
