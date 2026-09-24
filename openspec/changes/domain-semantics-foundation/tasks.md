## 1. EntityRef and Observation Model

- [ ] 1.1 Implement `EntityRef` and `Observation` models in a shared domain package or `geomemory.core.models`
- [ ] 1.2 Add tests verifying URI serialization, parsing, and equality

## 2. Temporal Model Semantics

- [ ] 2.1 Standardize temporal timestamp fields (`acquired_at`, `observed_at`, `published_at`, `ingested_at`, `created_at`) with validation in `geomemory` models
- [ ] 2.2 Update search and timeline filters to respect strict semantic roles

## 3. Label Taxonomy in GeoLearn

- [ ] 3.1 Implement `geolearn.labels` module (`LabelDefinition`, `LabelSet`, `LabelRegistry`) with predefined stress class taxonomy (`water_stress`, `nitrogen_deficiency`, `salinity_stress`, `healthy_canopy`)
- [ ] 3.2 Add unit tests verifying label registration, lookup, and versioning in `libs/geolearn/tests`
