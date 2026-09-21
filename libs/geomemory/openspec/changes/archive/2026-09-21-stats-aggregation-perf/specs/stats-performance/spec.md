## Purpose

Workspace statistics SHALL be computed efficiently using grouped SQL aggregates instead of per-revision sequential COUNT queries, ensuring sub-second response times even for workspaces with thousands of assets.

## ADDED Requirements

### Requirement: Stats queries use GROUP BY aggregation

The `Workspace.stats()` method SHALL compute segment, raster_scene, and vector_layer counts using `GROUP BY revision_id` queries rather than one `COUNT(*)` query per revision_id.

#### Scenario: Single aggregated query per table
- **WHEN** `stats()` is called on a workspace with any number of assets
- **THEN** exactly 3 aggregated COUNT queries are issued (one each for segment, raster_scene, vector_layer) plus the existing collection/asset/observation queries

#### Scenario: Correct counts preserved
- **WHEN** a workspace contains 50 assets with varying segment and layer counts
- **THEN** the returned stats dict contains the same totals as the pre-refactor implementation

#### Scenario: Empty workspace
- **WHEN** `stats()` is called on a workspace with zero assets
- **THEN** segment_count, scene_count, and layer_count are all 0
