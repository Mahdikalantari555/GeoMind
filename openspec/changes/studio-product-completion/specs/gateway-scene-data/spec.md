# gateway-scene-data — Spec Delta

## MODIFIED Requirements

### Requirement: Scene search carries preview metadata

Each search result SHALL include optional `preview_url` and `assets` from the
STAC item's thumbnail/rendered-preview assets; a missing asset SHALL yield
`null`, never a fabricated URL. Existing fields SHALL be unchanged.

#### Scenario: scene has a preview
- **WHEN** a STAC item has a `rendered_preview` asset
- **THEN** the result includes its URL as `preview_url`

### Requirement: Scene preview proxy

`GET /api/v1/data/scenes/{id}/preview` SHALL return the quicklook, fetched
server-side from an approved host without forwarding credentials or following
a redirect to an unapproved host; unknown scene / missing preview → 404.

### Requirement: Download result and composite tiles

The download result SHALL include `band_map: {name: 1_based_index}` for each
registered band. `GET /api/v1/data/composite/{z}/{x}/{y}.png` SHALL accept
workspace-relative `paths` and a comma-separated `bands` triple, stack them
into an RGB composite with per-channel stretch, and enforce sandbox containment
(403 outside). The single-band `/data/tiles` route SHALL remain supported.

#### Scenario: true-colour composite
- **WHEN** `bands=4,3,2` is requested with three valid band paths
- **THEN** a 256×256 three-channel PNG is returned

#### Scenario: out-of-sandbox path
- **WHEN** any path resolves outside the workspace
- **THEN** 403 `path_outside_sandbox` is returned
