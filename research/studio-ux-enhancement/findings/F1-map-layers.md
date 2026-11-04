# Findings: MapLibre Layer Synchronization & Map Viewport

## Root Causes Identified
1. `MapView.svelte` only creates a single GeoJSON source (`rois-source`) and two static layers (`rois-fill`, `rois-line`). When `mapState.layers` has raster scenes (`layer-eta-sample`) or products (`layer-farms-sample`), `MapView` completely ignores them — there is no sync loop for `mapState.layers`.
2. Visibility toggling in `LayerTree` changes `layer.visible` in the Svelte store, but `map.setLayoutProperty(id, 'visibility', 'visible' | 'none')` is never invoked.
3. Seeding a sample or adding an ROI leaves the camera fixed at zoom level 9 center `[48.68, 31.32]`. The sample ROI is located between `[48.62, 31.30]` and `[48.72, 31.38]`, so the user has no visual focus confirmation.

## Solution Architecture
1. **Dynamic Layer Manager Hook**:
   - For raster scenes: Add raster tile source / ImageSource with bounding coordinates and `raster` layer.
   - For vector parcels: Add GeoJSON source (`farms-source`) and `fill` + `line` layers.
   - Sync reactive effect: `$effect(() => { mapState.layers.forEach(...) })` updating visibility via `setLayoutProperty`.
2. **Camera Bounds Helper**:
   - `map.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding: 60, maxZoom: 14 })` automatically upon seeding sample or clicking ROI.
