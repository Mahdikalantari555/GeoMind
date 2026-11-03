# Specification: Geospatial Field Analytics & GIS Workspace

## Requirements

### Requirement 1: 3-Column Geospatial Layout (`delQN.jpg`)
The GIS interface MUST provide a three-column layout: layer tree, interactive map canvas, and parcel inspector.

#### Scenario: Selecting a field parcel
- **Given** the user is viewing the GIS workspace
- **When** clicking a parcel polygon on the map canvas
- **Then** the parcel polygon highlights with an emerald selection outline
- **And** the right-hand inspector populates with parcel metadata and crop indices.

### Requirement 2: Layer Tree & Opacity Controls
The left pane MUST provide layer visibility toggles and opacity sliders for all active raster and vector layers.

#### Scenario: Adjusting layer opacity
- **Given** the NDVI layer is visible
- **When** moving the layer opacity slider to 50%
- **Then** the map canvas updates layer transparency in real-time.

### Requirement 3: Bottom Analytics Dock with NDVI Curve
The interface MUST feature a collapsible bottom analytics dock rendering time-series vegetation indices.

#### Scenario: Inspecting parcel time-series
- **Given** a parcel is selected
- **When** opening the bottom analytics dock
- **Then** an NDVI historical time-series chart renders with data points, acquisition dates, and cloud cover flags
- **And** the METRIC ETa card displays daily actual evapotranspiration vs reference ET.

### Requirement 4: Camera Navigation from Citations & Search Hits
Selecting a spatial feature outside the map page MUST navigate to and focus the map canvas.

#### Scenario: Clicking a spatial citation
- **Given** a search hit or citation referencing a parcel or scene
- **When** the user clicks "View on Map"
- **Then** the application routes to the GIS workspace and smoothly zooms to the feature bounds.
