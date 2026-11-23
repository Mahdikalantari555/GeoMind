# ADR 0002 — Single-file Studio build

- Status: Accepted
- Date: 2026-11-23
- Scope: `apps/studio/vite.config.ts`, `apps/studio/index.html`
- Findings: PERF-02, S-017

## Context

Studio is deployed as a static front end for a locally-run gateway. Shipping a
separate JS/CSS bundle plus chunk files complicates air-gapped installation:
operators would have to copy an entire `dist/` tree and configure a web server
with correct MIME types and cache headers for every hashed asset.

## Decision

Use `vite-plugin-singlefile` to inline all JavaScript and CSS into one
`index.html`. The build output is a single artifact that can be opened from any
static host (or `file://` in demo mode) and that talks only to the gateway via
`API_BASE` (`/api/v1`, same origin or `VITE_GEOMIND_API`).

Tradeoffs, accepted deliberately:

- **Larger initial HTML** (~2 MB): acceptable for a local-first tool served on
  a LAN; gzip reduces transfer to ~0.6 MB. No code-splitting / lazy chunks.
- **Inline scripts require CSP `'unsafe-inline'`**: scoped to `script-src` and
  `style-src` only; `connect-src` stays `'self'` so no data leaves the origin.
- **The MapLibre worker is inlined as a `blob:` URL**: registered through
  `setWorkerUrl` and refcounted/revoked on teardown (see ADR 0001).

## Consequences

- Deployment is one file; there are no hashed chunks to manage.
- Any new third-party runtime dependency must be reviewed against the CSP and
  the data-sovereignty guarantee before being added.
- Source maps are not shipped; debugging uses the dev server.
