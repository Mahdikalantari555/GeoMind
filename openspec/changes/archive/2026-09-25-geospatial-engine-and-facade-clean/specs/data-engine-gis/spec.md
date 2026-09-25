## Purpose

Provides an authoritative, unified geospatial processing engine for remote sensing raster and vector calculations, including spectral indices, zonal statistics, polygonization, and projected area calculations via `geospatial_core`.

## ADDED Requirements

### Requirement: Unified spectral index calculation
The `geospatial_core` library SHALL provide authoritative calculators for spectral indices (including NDVI, EVI, NDWI, and SAVI) accepting NumPy band arrays and configurable nodata values, guaranteeing zero-division protection and numerical stability.

#### Scenario: Spectral index computation
- **WHEN** band arrays (NIR, Red, Green, Blue) are passed to the spectral index calculator
- **THEN** output float arrays are returned with finite numerical values and valid nodata masks

### Requirement: Core GIS operations
The `geospatial_core` library SHALL provide pure computational functions for raster zonal statistics over polygons, raster-to-vector polygonization, reclassification, and projected/geodesic area calculations.

#### Scenario: Zonal statistics extraction
- **WHEN** a single-band raster and a vector geometry are supplied
- **THEN** zonal summary statistics (mean, min, max, std, p05, p95, count) are computed without altering input data
