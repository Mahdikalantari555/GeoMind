# data-engine-gis Specification

## Purpose
Provides an authoritative, unified geospatial processing engine for remote sensing raster and vector calculations, including spectral indices, zonal statistics, polygonization, and projected area calculations via `geospatial_core`.

## Requirements

### Requirement: Unified spectral index calculation
The `geospatial_core` library SHALL provide authoritative calculators for spectral indices (including NDVI, EVI, NDWI, and SAVI) accepting NumPy band arrays and configurable nodata values, guaranteeing zero-division protection and numerical stability. The SAVI calculator SHALL accept `(nir, red, ...)` signature with NIR as the first positional argument, matching the convention of NDVI and EVI.

#### Scenario: Spectral index computation
- **WHEN** band arrays (NIR, Red, Green, Blue) are passed to the spectral index calculator
- **THEN** output float arrays are returned with finite numerical values and valid nodata masks

#### Scenario: SAVI signature convention
- **WHEN** `savi` is invoked with `(nir, red)` positional arguments
- **THEN** the index evaluates `(nir - red) / (nir + red + L) * (1 + L)` without sign inversion

### Requirement: Core GIS operations
The `geospatial_core` library SHALL provide pure computational functions for raster zonal statistics over polygons, raster-to-vector polygonization, reclassification with interval validation, and projected/geodesic area calculations supporting 2D/3D GeoJSON coordinates and polygon interior rings (holes).

#### Scenario: Zonal statistics extraction
- **WHEN** a single-band raster and a vector geometry are supplied
- **THEN** zonal summary statistics (mean, min, max, std, p05, p95, count) are computed without altering input data

#### Scenario: Reclassification invalid interval rejection
- **WHEN** reclassification rules contain an interval where `min >= max`
- **THEN** the function raises a `ValueError` indicating an invalid interval

#### Scenario: Geometry area with 3D coordinates and holes
- **WHEN** a GeoJSON geometry with 3D coordinates `[lon, lat, ele]` or interior hole rings is evaluated
- **THEN** area calculation succeeds without unpacking errors and subtracts hole areas from the exterior shell
