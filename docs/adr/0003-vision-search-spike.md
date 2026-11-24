# ADR 0003 — Vision search on the map: headless spike, no Studio view yet

- Status: Accepted (spike complete; UI deferred)
- Date: 2026-11-24
- Scope: `scripts/vision_search_spike.py`, `geomemory` image index seam
- Finding: F-096

## Context

The roadmap promises "pick a parcel/tile → find similar scenes/tiles" and
`docs/SPEC_SERVER.md:100` lists `POST /images/search`. In this checkout that
route does not exist (verified against the runtime OpenAPI), there is no cached
OLMoEarth checkpoint, the `[vision]` extra is not installed, the ONNX embedder
is text-only, `sample/` contains no imagery, and all `raster_tile.preview_path`
values in the local workspaces are `NULL`.

## Decision

1. Prove the bridge at the library seam, not through a nonexistent route.
   `geomemory`'s `VisionEmbedder` protocol → `ImageIndex.upsert/save` →
   `GeoMemory.search_images(vector)` is the contract a future gateway route
   would call. No library internals were forked; no `libs/geomemory` change was
   needed.
2. Use **tile granularity**. `raster_tile` rows already carry a window + transform
   and a provenance chain to `raster_scene → asset_revision → asset`, so a tile
   id is a valid, traceable search target. Scene granularity would require a new
   aggregation definition.
3. Run the spike offline with a deterministic downsample+L2 embedder over the
   eight Landsat band GeoTIFFs in `geomemorytest/data`. Results are in
   `docs/spikes/vision-search.json`: self-retrieval top-1 = 1.000, near-duplicate
   ranked second, identical results on repeat, all target ids resolvable.
4. **Stop before the Studio view.** The spike proves transport only. Without a
   real vision checkpoint there is no semantic-quality result, and shipping a
   UI off a hash-like embedder would be a false promise.

## Prerequisites before a Studio view (all currently unmet)

- Add `POST /api/v1/images/search` with a validated request schema (tile id or
  base64 image bytes) and a threadpool call to `ws.search_images`.
- Cache a real OLMoEarth checkpoint offline and install the `[vision]` extra;
  persist tile previews (`build_tiles` with an artifact dir, not
  `window_only_tiles`) and build a real image index.
- Measure quality: near-duplicate tiles must rank above random tiles.
- Only then define the Studio interaction (click tile → search → ranked results
  with provenance) as a separate change.

## Consequences

- The differentiating view is explicitly not claimed as shipped.
- The headless bridge is reusable as the implementation seed when the
  prerequisites land.
