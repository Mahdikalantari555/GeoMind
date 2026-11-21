# Spec: studio-map-layers

## Purpose
Ensure all layers added to `mapState.layers` visually appear on the MapLibre canvas and respond in real-time to sidebar visibility/opacity controls.

## Requirements

### Requirement: Reactive Layer Sync
`MapView.svelte` SHALL watch `mapState.layers` and dynamically add/update MapLibre sources and layers for all registered items:
- Raster scene layers: rendered as raster overlays with configurable opacity.
- Vector product layers (farm parcels): rendered as GeoJSON polygon fills and borders.
- ROI layers: rendered with distinct teal borders and translucent fills.

### Requirement: Real-Time Visibility & Opacity
Toggling a checkbox or dragging an opacity slider in `LayerTree.svelte` SHALL instantly update the corresponding MapLibre layer's `visibility` layout property and paint opacity property without re-initializing the map instance.

### Requirement: Camera Auto-Fit
When an ROI is selected, drawn, or loaded from a workspace, the map camera SHALL automatically pan and zoom (`fitBounds`) to enclose the feature geometry with smooth animation and padding.
