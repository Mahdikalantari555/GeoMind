# ADR 0001 — Sovereign basemap and glyph sources

- Status: Accepted
- Date: 2026-11-23
- Scope: `apps/studio`, `server/src/geofront_api/routers/data.py`
- Findings: S-016, S-017

## Context

Studio originally pointed MapLibre directly at Esri, OpenTopoMap, CARTO and
`demotiles.maplibre.org`. Every pan/zoom disclosed the viewport (and, by
inference, the user's ROI) to third parties and made the map unusable in an
air-gapped deployment. The single-file HTML also had no CSP while loading the
MapLibre worker from an inlined `blob:` URL.

## Decision

1. The browser never requests a basemap tile or glyph from a third party.
   MapLibre requests gateway routes instead:

   - `GET /api/v1/data/maps/tiles/{provider}/{z}/{x}/{y}.png`
   - `GET /api/v1/data/maps/glyphs/{fontstack}/{range}.pbf`

2. The gateway fetches from operator-configured upstream templates, read from
   the environment at call time:

   - `GEOMIND_BASEMAP_SATELLITE_URL`
   - `GEOMIND_BASEMAP_TOPO_URL`
   - `GEOMIND_BASEMAP_GRAY_URL`
   - `GEOMIND_GLYPHS_URL`

   Each template uses `{z}`, `{x}`, `{y}` (tiles) or `{fontstack}`, `{range}`
   (glyphs). Upstreams must be HTTPS, or plain HTTP for loopback only; embedded
   credentials, query strings and redirects to unapproved hosts are rejected.

3. Defaults point at public HTTPS providers for connected deployments. This is
   a convenience, **not a requirement**: an air-gapped operator sets the env
   vars to a local tile/glyph server (or an offline pack) and the map renders
   without any third-party request.

4. Offline/demo mode uses a blank inline tile, so the map still renders with its
   background layer and workspace overlays with no network access.

5. The single-file HTML declares a CSP restricting `default-src`/`connect-src`
   to the gateway origin and permitting `blob:` solely for the inlined worker.
   The worker blob URL is refcounted and revoked when the last map unmounts.

## Consequences

- All map traffic is observable and controllable at the gateway, consistent
  with the data-sovereignty guarantee.
- Operators must supply local upstream templates for fully offline use.
- The CSP forbids `eval` and third-party `connect-src`; any future external
  integration must be added here explicitly.
