# studio-acquire — Spec Delta

## MODIFIED Requirements

### Requirement: One Landsat 8/9 option

The sensor selector SHALL offer a single "Landsat 8/9 (Collection 2 L2)" option
that searches the combined `landsat-c2-l2` collection and returns both LC08 and
LC09 scenes. No client-side dedupe is required (STAC ids are globally unique).

### Requirement: Scene result preview

The Acquire page SHALL render a real thumbnail from the gateway preview proxy
for every result with a preview URL, and an explicit "no preview available"
state otherwise. Generated gradient thumbnails SHALL appear only in clearly
labelled demo/synthetic mode and SHALL NOT be presented as real imagery.

#### Scenario: live result shows a quicklook
- **WHEN** search returns a scene with a preview URL
- **THEN** the card renders an `<img>` pointing at the gateway preview route

### Requirement: Custom RGB band selection

After download the user SHALL select R/G/B bands from per-sensor presets or
individual band names; the choice SHALL persist on the layer and rebuild the
tile URL with the selected indices. The default single-band preview SHALL remain
for backward compatibility until the user chooses a composite.

#### Scenario: false colour switch
- **WHEN** the user selects R=5, G=4, B=3 on a Landsat layer
- **THEN** the layer tile URL requests `bands=5,4,3`

### Requirement: Per-layer tile errors

Tile errors SHALL be tracked per source id with a per-layer warning and retry,
independent of basemap retry, so a broken band path is not rendered as an empty
map. Download dedup keys SHALL be built from the captured search ROI.
