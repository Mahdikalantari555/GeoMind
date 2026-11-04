# Proposal: add-studio-map-layers

## Intent
Make all map layers (raster scene overlays, vector parcel geometries, and drawn ROIs) visually rendered on the MapLibre GL canvas with reactive visibility, opacity controls, and camera bounding box auto-fit.

## Scope
1. Wire `MapView.svelte` to dynamically mount raster and GeoJSON sources from `mapState.layers`.
2. Add reactive visibility sync (`map.setLayoutProperty(id, 'visibility', 'visible' | 'none')`) and opacity control (`map.setPaintProperty(id, 'raster-opacity', opacity)`).
3. Implement `map.fitBounds` when an ROI is created or the sample workspace is loaded.
4. Support raster mock tiles / image overlay rendering for the Landsat 9 ETa demo product.
