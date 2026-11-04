# Tasks: add-studio-map-layers

## 1. Dynamic MapLibre Source & Layer Binding
- [ ] 1.1 Extend `MapLayer` type in `apps/studio/src/lib/stores/map.svelte.ts` with `sourceType: 'geojson' | 'raster' | 'image'`, `sourceData: unknown`, and `opacity: number`.
- [ ] 1.2 Implement dynamic layer reconciliation in `MapView.svelte`: on `mapState.layers` mutation, add missing MapLibre sources/layers and remove stale ones.
- [ ] 1.3 Add reactive visibility and opacity watchers issuing `map.setLayoutProperty` and `map.setPaintProperty`.

## 2. Sample Workspace Layer Geometries
- [ ] 2.1 Update `SAMPLE_WORKSPACE` in `sampleWorkspace.ts` to include valid GeoJSON coordinates for `layer-farms-sample` and bounding coordinates for `layer-eta-sample`.
- [ ] 2.2 Seed both vector and raster layers with real visual coordinates during `seedSampleWorkspace()`.

## 3. Camera Auto-Fit
- [ ] 3.1 Implement `fitToGeometry(coordinates)` in `MapView.svelte` using `map.fitBounds` with 60px padding.
- [ ] 3.2 Trigger `fitToGeometry` on initial sample load and whenever `mapState.currentRoi` changes.

## 4. UI Layer Controls & Quality Gates
- [ ] 4.1 Add opacity slider and color tag indicators in `LayerTree.svelte`.
- [ ] 4.2 Write unit tests in `map.test.ts` for layer opacity and source registration.
- [ ] 4.3 Validate with `pnpm check && pnpm lint && pnpm test`.
