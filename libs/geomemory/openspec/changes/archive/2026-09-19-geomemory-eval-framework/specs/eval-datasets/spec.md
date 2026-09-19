## Purpose

Defines the in-repo evaluation dataset layout: directory structure, per-dataset
benchmark queries contract, and dataset manifest. Datasets live at
`geomemory-evals/datasets/<name>/` and are ingested through the production
pipeline unchanged.

## ADDED Requirements

### Requirement: Dataset directory structure
The system SHALL recognize a dataset as a directory under `geomemory-evals/datasets/`
containing ingestible sources and a `queries.yaml`.

#### Scenario: Valid dataset
- **WHEN** a directory under `geomemory-evals/datasets/` contains a `queries.yaml`
- **THEN** it is a valid benchmark dataset eligible for `eval rebuild` / `eval stats`

#### Scenario: Invalid dataset
- **WHEN** a directory under `geomemory-evals/datasets/` has no `queries.yaml`
- **THEN** it is rejected with a clear error naming the missing file

### Requirement: Benchmark queries contract
Each dataset's `queries.yaml` SHALL be a mapping with a top-level `queries` list of
strings. Optional `name` and `description` fields are permitted.

#### Scenario: Query execution
- **WHEN** `queries.yaml` lists `["What is METRIC?"]`
- **THEN** each entry is executed verbatim through the standard retrieval pipeline

#### Scenario: Empty queries
- **WHEN** `queries` is an empty list
- **THEN** the dataset is still valid but produces no per-query artifacts

### Requirement: Dataset manifest
Each dataset MAY carry a `manifest.yaml` describing its composition: source file
list, modality mix, and intended coverage. When present, the manifest SHALL
describe every source file in the dataset.

#### Scenario: Manifest present
- **WHEN** `manifest.yaml` exists alongside `queries.yaml`
- **THEN** its contents are recorded in run metadata for traceability

#### Scenario: Manifest absent
- **WHEN** no `manifest.yaml` is present
- **THEN** the dataset is still valid; run metadata records `manifest: null`

### Requirement: Accepted source formats
Datasets SHALL contain only formats the production pipeline accepts: `.txt`,
`.md`, `.html`, `.pdf`, `.docx`, `.py`, `.js`, `.mjs`, `.gee`, `.ipynb`,
`.tif`/`.tiff`, `.geojson`, and `.shp`.

#### Scenario: Unsupported format in dataset
- **WHEN** a dataset directory contains a file the pipeline cannot route
- **THEN** ingestion reports it as an error rather than silently skipping it

### Requirement: Dataset size bound
Datasets SHALL remain small enough for local execution; binary assets
(GeoTIFF, PDF) are kept minimal.

#### Scenario: Size check
- **WHEN** a dataset exceeds the configured size threshold
- **THEN** a warning is emitted during rebuild but execution continues