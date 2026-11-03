# Tasks: geospatial-field-analytics

- [ ] 1. 3-Column Layout & Layer Tree (`delQN.jpg`)
  - [ ] 1.1 Refactor `MapsPage.tsx` into a 3-column instrument layout.
  - [ ] 1.2 Implement `LayerTree.tsx` with layer visibility checkboxes, color ramps, and opacity sliders.
- [ ] 2. Map Canvas & Parcel Vector Layer
  - [ ] 2.1 Render vector parcel boundaries with hover and selection styles.
  - [ ] 2.2 Wire click events to update selected parcel state.
- [ ] 3. Parcel Inspector Panel
  - [ ] 3.1 Build `ParcelInspector.tsx` showing crop type, area, planting date, and current agronomic index values.
  - [ ] 3.2 Add quick actions (Export Parcel GeoJSON, Run Playbook on Parcel).
- [ ] 4. Bottom Analytics Dock
  - [ ] 4.1 Build collapsible `AnalyticsDock.tsx` anchored to bottom.
  - [ ] 4.2 Build `NdviTimeSeriesChart.tsx` SVG chart with date ticks and hover tooltip.
  - [ ] 4.3 Build `MetricEtaCard.tsx` with water consumption gauges and stress indicators.
- [ ] 5. Search & Agent Integration
  - [ ] 5.1 Add "Fly to Feature" bridge from search hits and citation drawer to map view.
- [ ] 6. Testing & Verification
  - [ ] 6.1 Unit tests for layer toggle state and parcel selection.
  - [ ] 6.2 Visual and layout verification against mockup `delQN.jpg`.
