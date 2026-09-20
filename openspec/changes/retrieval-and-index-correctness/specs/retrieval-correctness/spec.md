## Purpose

Define observable correctness guarantees for the retrieval and indexing pipeline — vision embedding dimensions, segment null-safety, and search result validity.

## ADDED Requirements

### Requirement: Vision embedding dimension SHALL match actual vector size
`vision_embed.py` SHALL determine the embedding dimension from the actual vector data, not from `index.ids()[0].shape[-1]` (which operates on string IDs and always raises AttributeError, defaulting to 128).

#### Scenario: Correct dimension for OLMoEarth Nano
- **WHEN** a GeoTIFF asset is ingested with vision embedding enabled and OLMoEarth Nano is configured
- **THEN** the image index manifest SHALL record `dimension=768` (the actual OLMoEarth output dimension)
- **AND** subsequent image searches SHALL compute cosine similarity in 768-dimensional space

#### Scenario: Dimension read from vector, not ID
- **WHEN** `vision_embed.py` accesses the index to determine dimension
- **THEN** it SHALL read from `index.vector(0)` or equivalent vector-access method, NOT from `index.ids()`
- **AND** if the vector access fails, it SHALL fall back to a documented default AND log a warning

### Requirement: segment_ids SHALL be null-safe during ingest
`workspace.py:_ingest()` SHALL ensure `segment_ids` is always a list before any `.append()` call, even when `_segments_for_revision()` returns None.

#### Scenario: Non-dedup ingest path
- **WHEN** a file is ingested and the dedup check finds no existing revision
- **THEN** `segment_ids` SHALL be initialized as `[]` before the segment creation loop
- **AND** no `AttributeError: 'NoneType' object has no attribute 'append'` SHALL occur

### Requirement: Image search SHALL abstain on zero-vector fallback
`image_backend.py:_query_vector()` SHALL return an empty hit list (not nearest-random-tiles) when cross-modal encoding is unavailable and the zero-vector fallback would trigger.

#### Scenario: Vision index exists but embedder unavailable
- **WHEN** `_image_search()` is called and the vision embedder cannot produce a query vector
- **THEN** the method SHALL return `[]` (empty hits)
- **AND** a warning SHALL be logged indicating the vision embedder is unavailable
- **AND** the text/dense search results SHALL still be returned normally (graceful degradation)

### Requirement: Single SearchService canonical path
There SHALL be exactly one importable `SearchService` class that handles all search parameters including `modalities` and `modality_weight`.

#### Scenario: Multimodal search reaches retrieval layer
- **WHEN** `Workspace.search(modalities="both", modality_weight=0.8)` is called
- **THEN** both parameters SHALL reach `retrieval/search_service.SearchService.search()`
- **AND** image hits SHALL be weighted by 0.8 in the RRF fusion

## MODIFIED Requirements

### Requirement: SearchService wrapper removal
The thin wrapper in `geomemory/services/search_service.py` SHALL be deleted. All callers SHALL use `geomemory.retrieval.search_service.SearchService` directly or go through `Workspace.search()`.

#### Scenario: No external imports of deleted module
- **WHEN** the wrapper module is removed
- **THEN** `grep -rn "geomemory.services.search_service" .` across the monorepo SHALL return zero results
- **AND** `pytest libs/geomemory/tests -q` SHALL pass without modification
