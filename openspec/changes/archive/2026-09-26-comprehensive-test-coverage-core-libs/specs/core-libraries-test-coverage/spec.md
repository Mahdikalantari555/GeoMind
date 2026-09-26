## Purpose

Guarantees high test reliability and regression protection by enforcing a strict >95% test coverage threshold across core libraries.

## ADDED Requirements

### Requirement: Geospatial Core test coverage exceeds 95%
The `geospatial_core` test suite SHALL execute and cover at least 95% of statements in `libs/geospatial_core/src/geospatial_core`, including polygonization, area calculations across single and multi-polygons with holes, and CRS parsing.

#### Scenario: Verify geospatial_core coverage
- **WHEN** `pytest libs/geospatial_core/tests --cov=libs/geospatial_core/src/geospatial_core` is executed
- **THEN** statement coverage exceeds 95% and all tests pass

### Requirement: GeoDomain test coverage exceeds 95%
The `geodomain` test suite SHALL execute and cover at least 95% of statements in `libs/geodomain/src/geodomain`, including identity validation, observation models, and temporal windows.

#### Scenario: Verify geodomain coverage
- **WHEN** `pytest libs/geodomain/tests --cov=libs/geodomain/src/geodomain` is executed
- **THEN** statement coverage exceeds 95% and all tests pass

### Requirement: GeoLearn test coverage exceeds 95%
The `geolearn` test suite SHALL execute and cover at least 95% of statements in `libs/geolearn/src/geolearn`, including confidence calibration curves, Page-Hinkley drift detection, streaming sliding windows, hierarchical regional models, edge export, and model versioning/rollback.

#### Scenario: Verify geolearn coverage
- **WHEN** `pytest libs/geolearn/tests --cov=libs/geolearn/src/geolearn` is executed
- **THEN** statement coverage exceeds 95% and all tests pass

### Requirement: GeoAgent test coverage exceeds 95%
The `geoagent` test suite SHALL execute and cover at least 95% of statements in `libs/geoagent/src/geoagent`, including CLI commands, LLM backends, playbooks, tool registries, and GeoLearn tool integrations.

#### Scenario: Verify geoagent coverage
- **WHEN** `pytest libs/geoagent/tests --cov=libs/geoagent/src/geoagent` is executed
- **THEN** statement coverage exceeds 95% and all tests pass

### Requirement: GeoMemory test coverage exceeds 95%
The `geomemory` test suite SHALL execute and cover at least 95% of statements in `libs/geomemory/src/geomemory`, including workspace lifecycles, vector/embedding backends, retrieval filters, ingestion loaders, QA service abstention, and CLI command groups.

#### Scenario: Verify geomemory coverage
- **WHEN** `pytest libs/geomemory/tests --cov=libs/geomemory/src/geomemory` is executed
- **THEN** statement coverage exceeds 95% and all tests pass
