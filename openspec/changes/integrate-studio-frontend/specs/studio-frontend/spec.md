# Capability: studio-frontend

## Summary
Complete implementation of GeoMind Studio front end satisfying the "One app, one map, one loop" vision.

## Requirements

### Requirement: Map Canvas as Home
- The root route `/` MUST display the Map Canvas as the primary viewport.
- The map MUST be powered by MapLibre GL with offline fallback synthetic rasters.
- The user MUST be able to toggle raster overlays (NDVI, ETa, True Color, Hillshade) with continuous opacity controls and gradient legends.
- The user MUST be able to draw BBox and Polygon ROIs, view real-time computed area in hectares, and save them with custom names.

### Requirement: Acquire Data Engine
- The `/acquire` view MUST allow selecting active ROI, sensor (Landsat 8/9, Sentinel-2), date range, and cloud cover threshold.
- The view MUST display search results with quicklook previews and acquisition metadata.
- Initiating a download MUST trigger a background job and display real-time stepwise progress (bands fetch → COG conversion → ingestion).
- Completed downloads MUST automatically register as raster layers in the Map Layer Tree.

### Requirement: Ingestion & Resources
- The `/resources` view MUST provide drag-and-drop file ingestion for `.pdf`, `.tif`/`.tiff`, `.geojson`, and `.csv`.
- Ingested assets MUST be content-addressed by SHA-256 and display modality type (`text.*` vs `vision.*`).
- The pipeline progress MUST visualize chunking, embedding, and vector index registration.

### Requirement: Grounded QA & Provenance
- The `/knowledge` view MUST support Hybrid, Semantic, and Keyword search modes.
- Generated answers MUST contain interactive citation chips linking claims directly to cited segments in a split-screen Provenance Drawer.
- If retrieval score fails to exceed the grounding threshold, the system MUST render an explicit Abstention card and refuse hallucinated synthesis.

### Requirement: Training Lab & Feedback Loop
- The `/training` view MUST maintain a review queue of model predictions with Accept, Reject, and Correct actions.
- The user MUST be able to initiate 1-click CPU `partial_fit` training.
- The view MUST display batch progress, accuracy deltas, and model version history with 1-click rollback capability.

### Requirement: Agent Rail & Parity
- The Agent Rail MUST be dockable and collapsible from any view via `Ctrl/Cmd+B`.
- The agent MUST support token streaming, visible tool call execution cards with execution duration, and pre-configured playbooks (ETa, NDVI anomaly, water balance).
- The agent MUST possess parity with UI actions (e.g., creating ROIs directly on the MapCanvas).

### Requirement: Localization & Accessibility
- The application MUST provide instant switching between English (LTR) and Persian (RTL).
- When in RTL mode, all chrome and sidebars MUST mirror using logical CSS properties (`ms-*`, `me-*`, `start-*`, `end-*`).
- The map canvas coordinate system and pan/zoom interactions MUST remain in geographic LTR in all languages.
