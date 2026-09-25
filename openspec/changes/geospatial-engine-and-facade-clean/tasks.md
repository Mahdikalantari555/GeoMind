## 1. Shared Geospatial Core (`libs/geospatial_core`)

- [ ] 1.1 Scaffold `libs/geospatial_core` with `pyproject.toml` (NumPy, SciPy, Rasterio, GeoPandas)
- [ ] 1.2 Implement spectral indices (`ndvi`, `evi`, `ndwi`, `savi`) with nodata handling and zero-division protection
- [ ] 1.3 Implement GIS utilities: `zonal_stats`, `polygonize`, `reclassify`, geodesic/metric area calculations, and CRS helpers
- [ ] 1.4 Add comprehensive unit tests in `libs/geospatial_core/tests`

## 2. Refactor Consuming Libraries

- [ ] 2.1 Refactor `geomemory.rs.raster.spectral` to delegate to `geospatial_core` (preserving ARCHITECTURE §3.3)
- [ ] 2.2 Refactor `geoagent.tools.gis_tools` to delegate to `geospatial_core`
- [ ] 2.3 Refactor `data_engine.surface.vegetation` to consume `geospatial_core`

## 3. GeoMemory Facade & GeoLearn Decoupling

- [ ] 3.1 Implement `list_candidate_memories` on `GeoMemory` facade in `libs/geomemory/src/geomemory/core/workspace.py`
- [ ] 3.2 Refactor `geolearn.training_pipeline` to use `ws.list_candidate_memories()` and eliminate direct SQLite access to `geomemory.db`
- [ ] 3.3 Verify with `pytest libs/geolearn/tests` and `pytest libs/geomemory/tests`
