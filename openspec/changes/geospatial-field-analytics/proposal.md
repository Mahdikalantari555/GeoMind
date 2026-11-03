# Proposal: geospatial-field-analytics

## Why
Remote sensing researchers and agronomic analysts work visually with satellite rasters and parcel vectors. As designed in mockup `delQN.jpg`, GeoMind requires a dedicated 3-column GIS workspace with layer controls, farm parcel selection, metadata inspector, and an expandable bottom analytics dock displaying time-series NDVI curves and METRIC ETa water balance cards.

## What Changes
1. **3-Column GIS Workspace (`delQN.jpg`)**:
   - Left column: Hierarchical layer tree (Sentinel-2 True Color, NDVI Index, LST Thermal, METRIC ETa, Field Boundaries).
   - Center column: Interactive MapLibre/Leaflet map canvas with vector parcel geometries, hover highlights, and layer opacity controls.
   - Right column: Selected parcel inspector (Parcel ID, crop type, planting date, mean NDVI, daily ETa, soil moisture estimation).

2. **Bottom Analytics Dock**:
   - Collapsible analytics drawer anchored to the bottom of the map view.
   - Interactive NDVI time-series chart (SVG/Canvas) showing historical vegetation trajectory with cloud mask flags.
   - METRIC ETa water consumption card (daily actual ET vs reference ET, water stress indicator).

3. **Search-to-Map Navigation Bridge**:
   - Clicking a geographic search hit, citation, or agent artifact automatically flies the map camera to the target feature's bounding box and selects it.

## Invariants & Guardrails
- GIS map view must remain performant with at least 500 vector polygons.
- Map controls must support RTL mirroring in Persian (`fa`).
- Raster tiles and vectors must be cached locally to allow offline analysis.
