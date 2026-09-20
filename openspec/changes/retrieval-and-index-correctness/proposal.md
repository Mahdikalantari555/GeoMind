## Why

Three independent correctness bugs in geomemory's retrieval and indexing pipeline produce silently wrong results: (1) vision embedding dimension defaults to 128 instead of the actual 768 because `.shape[-1]` is called on a string ID, (2) `segment_ids` can be `None` when appended to during ingest causing a runtime crash, and (3) the placeholder vision embedder returns zero vectors producing random tile matches. Additionally, the double `SearchService` naming creates API confusion about which class is canonical.

## What Changes

- Fix `vision_embed.py:89`: read embedding dimension from the actual vector, not from `index.ids()[0].shape[-1]`
- Fix `workspace.py:338`: guard `segment_ids` against None before append
- Fix `image_backend.py`: replace zero-vector fallback with proper abstention (return empty hits) instead of returning nearest-random tiles
- Unify SearchService: delete the thin wrapper in `services/search_service.py` or make it delegate fully
- Add regression tests for each fix

## Capabilities

### New Capabilities
- `retrieval-correctness`: Vision embedding dimensions SHALL be read from actual embedding vectors, not inferred from ID strings. Search results SHALL never contain zero-vector matches.

### Modified Capabilities
- `search-service`: The public `SearchService` entry point SHALL expose all parameters (`modalities`, `modality_weight`) consistently.

## Impact

| Area | Detail |
|---|---|
| `libs/geomemory/src/geomemory/ingest/vision_embed.py:89` | Fix dimension detection |
| `libs/geomemory/src/geomemory/core/workspace.py:338` | Null-safety guard |
| `libs/geomemory/src/geomemory/index/image_backend.py` | Zero-vector → abstention |
| `libs/geomemory/src/geomemory/services/search_service.py` | Delete or unify |
| Tests | New regression tests for each fix |
