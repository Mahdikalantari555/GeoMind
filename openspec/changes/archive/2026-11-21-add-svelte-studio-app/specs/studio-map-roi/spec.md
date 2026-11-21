# studio-map-roi

## Purpose

Define the map home of GeoMind Studio: the layer tree, map rendering, and
ROI drawing. The old app "had no maps available" — this capability makes the
map the load-bearing, always-working surface.

## ADDED Requirements

### Requirement: Map canvas is the home route
The home route SHALL render a MapLibre GL map filling the viewport. The map
SHALL render without any API key or paid tile service, using a bundled
offline-capable basemap style.

#### Scenario: First load, offline
- **WHEN** the app loads with no internet access
- **THEN** the map still renders using the offline fallback basemap

### Requirement: Layer tree
A layer panel SHALL list all layers grouped by: Base, Scenes, Products,
Document overlays, and ROIs. Each layer SHALL have a visibility toggle, and
groups SHALL be collapsible with state persisted per workspace.

#### Scenario: Toggle a scene layer
- **WHEN** the user toggles a raster scene layer off
- **THEN** the layer disappears from the map immediately and stays hidden
  after reload

### Requirement: ROI drawing
The map SHALL provide ROI drawing tools: polygon and bounding box. A drawn
ROI SHALL be nameable, saved via the gateway, and rendered on the map with
its geometry, name, and geodesic area.

#### Scenario: Draw and save a polygon ROI
- **WHEN** the user completes a polygon and confirms the name
- **THEN** the ROI persists (visible after reload) with its area shown in
  the layer tree

### Requirement: ROI is a first-class object
ROIs SHALL be listable, renamable, deletable, and selectable. Selecting a ROI
SHALL set the "current ROI" that the Acquire page (and later agent tools)
operate on.

#### Scenario: Select an existing ROI
- **WHEN** the user selects a saved ROI
- **THEN** the map flies to it and the Acquire page targets it

### Requirement: Scene layers appear automatically
When a downloaded scene finishes ingest (per `studio-acquire`), its raster
SHALL appear as a layer under Scenes without manual refresh, driven by SSE
events — not polling.

#### Scenario: Download completes
- **WHEN** a download job finishes and ingest completes
- **THEN** the new scene layer appears in the tree and on the map without a
  page reload
