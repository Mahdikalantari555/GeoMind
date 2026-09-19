## Purpose

Delta: adds Shapefile ingestion to the existing ingestion capability. Shapefiles
(`.shp`) route through the loader registry and produce typed segments like
other spatial sources.

## MODIFIED Requirements

### Requirement: Format routing
The system SHALL detect MIME type by extension and route to loaders: text, code,
PDF (pymupdf), GeoJSON, GeoTIFF, and Shapefile — producing typed segments
(`paragraph`, `table`, `formula`, `code_unit`, `heading`, `cell`).

#### Scenario: Document chunking
- **WHEN** a text/PDF/code source is ingested
- **THEN** header-preserving or fixed-size chunking produces segments with locators

#### Scenario: Unsupported format
- **WHEN** MIME/kind cannot be resolved
- **THEN** `UnsupportedFormatError` is raised

#### Scenario: Shapefile ingest
- **WHEN** a `.shp` file is ingested (with `rs` extra installed)
- **THEN** the ShapefileLoader parses geometry and attributes into typed segments
  and persists a `vector_layer` row with spatial index entries

#### Scenario: Shapefile without rs extra
- **WHEN** a `.shp` file is ingested and the `rs` extra is not installed
- **THEN** ingestion fails with a clear error indicating the missing optional dependency

#### Scenario: Shapefile sidecar files
- **WHEN** a `.shp` is ingested alongside `.shx`, `.dbf`, and `.prj` sidecars
- **THEN** all sidecars are consumed as part of the single shapefile source

## ADDED Requirements

### Requirement: Shapefile loader registration
The system SHALL register a ShapefileLoader for shapefile media in the default
loader registry, requiring the `rs` optional extra.

#### Scenario: Loader resolves
- **WHEN** a `.shp` source is resolved through the default registry
- **THEN** the ShapefileLoader is returned

#### Scenario: Loader gated on rs extra
- **WHEN** the `rs` extra is absent
- **THEN** importing the ShapefileLoader raises a clear `RuntimeError` naming the
  missing dependency rather than an opaque import failure