# Research Brief: GeoMind Studio Layer Rendering & Research Agent UX

**Date:** 2026-11-04  
**Topic:** Resolving layer visibility on MapLibre and upgrading guided question / research assistant into full instrument rail UX according to target mockups (`/mnt/c/Users/ASUS/Desktop/geomind-design/`).  
**Mode:** standard  

## Problem Statement
1. In `MapView.svelte`, layers added to `mapState.layers` (e.g. raster scenes, vector field boundaries) are tracked in the sidebar `LayerTree`, but never wired to MapLibre GL sources or layers on the canvas. Additionally, when a user seeds a workspace or adds an ROI, the map camera does not fit bounds to the ROI/layers.
2. The Guided Question flow is currently a floating popover widget in the bottom-right corner rather than the collapsible, full-height docked Agent Rail specified in the startup vision and visual mockups. Citations lack bidirectional interactivity (clicking citation should pan/zoom map or highlight feature).

## Scope Boundaries
- **In Scope:**
  - MapLibre GL dynamic layer syncing (raster overlays, GeoJSON vector layers, layer opacity, camera flyTo/fitBounds).
  - Docked Right-Rail Agent interface replacing floating card: expandable drawer, streaming token simulation/SSE hooks, question presets, and clickable citation chips that interact with map layers.
  - Designing modular OpenSpec changes for progressive implementation.
- **Out of Scope:**
  - Redesigning gateway server algorithms (already complete).
  - Rewriting Svelte 5 runes architecture.

## Angles
1. **Angle 1:** MapLibre GL reactive layer synchronization in Svelte 5 (vector GeoJSON + raster tiles/image sources, visibility toggling, opacity control, and automated bounding box fit).
2. **Angle 2:** Instrument Agent Rail UX (docked right sidebar, chat history, prompt templates, grounded citation chips, token stream rendering).
3. **Angle 3:** OpenSpec change breakdown for modular, verifiable delivery.
