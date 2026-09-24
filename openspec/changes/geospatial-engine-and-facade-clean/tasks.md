## 1. Data Engine GIS Consolidation

- [ ] 1.1 Create `data_engine.gis` containing `zonal_stats`, `polygonize`, `reclassify`, and area calculation functions with tests in `libs/data_engine/tests`
- [ ] 1.2 Unify spectral indices (`NDVI`, `EVI`, `NDWI`, `SAVI`) in `data_engine.surface.vegetation` with comprehensive formula tests

## 2. GeoAgent and GeoMemory Delegation

- [ ] 2.1 Refactor `geoagent.tools.gis_tools` to delegate all calculations to `data_engine` and verify `pytest libs/geoagent/tests/test_gis_tools.py`
- [ ] 2.2 Refactor `geomemory.rs.raster.spectral` to delegate to `data_engine` with fallback

## 3. GeoMemory Facade & GeoLearn Decoupling

- [ ] 3.1 Implement `list_candidate_memories` on `GeoMemory` facade in `libs/geomemory/src/geomemory/core/workspace.py`
- [ ] 3.2 Refactor `geolearn.training_pipeline` to use `ws.list_candidate_memories()` and eliminate direct SQLite access to `geomemory.db`
- [ ] 3.3 Verify with `pytest libs/geolearn/tests` and `pytest libs/geomemory/tests`
