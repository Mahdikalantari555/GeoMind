## 1. Pure Domain Library (`libs/geodomain`)

- [x] 1.1 Scaffold `libs/geodomain` with `pyproject.toml` (Pydantic v2 only, no DB/IO/ML)
- [x] 1.2 Implement `EntityRef` and `GeoURI` parser/serializer supporting `geo:<type>/<id>`
- [x] 1.3 Implement `Observation`, `ObservationRef`, and `ObservationKind` models
- [x] 1.4 Implement `TemporalKinds` with strict UTC ISO-8601 validation
- [x] 1.5 Implement `geodomain.labels` (`LabelDefinition`, `LabelSet`, `LabelRegistry`) with predefined stress class taxonomy (`water_stress`, `nitrogen_deficiency`, `salinity_stress`, `healthy_canopy`)
- [x] 1.6 Add comprehensive unit test suite in `libs/geodomain/tests`

## 2. GeoMemory Observation Migration

- [x] 2.1 Migrate `geomemory.core.models.Observation` to import and extend/re-export `geodomain.Observation`
- [x] 2.2 Update `geomemory.storage.repositories.spatial_repo` to work seamlessly with migrated `Observation`
- [x] 2.3 Verify `geomemory` tests pass: `conda run -n geospatial pytest libs/geomemory/tests`

## 3. Cross-Library Integration

- [x] 3.1 Integrate `geodomain` into `geoagent` tools and models
- [x] 3.2 Integrate `geodomain` into `data_engine` scene readers and metadata
- [x] 3.3 Integrate `geodomain.labels` into `geolearn` for feedback classification
