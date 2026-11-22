# studio-shell — Spec Delta

## MODIFIED Requirements

### Requirement: Settings persistence

Grounding and classifier thresholds changed in Settings/Training SHALL be
persisted via `PUT /workspace/settings` (debounced) and hydrated on workspace
refresh; reload SHALL NOT silently restore defaults. Pure UI preferences MAY
remain local.

### Requirement: Sovereign map sources and CSP

Basemap tiles and glyphs SHALL NOT be requested from third-party hosts by the
browser; they SHALL be proxied through the gateway from an operator-configured
source or served from an offline tile pack, recorded in an ADR. The single-file
HTML SHALL declare a CSP permitting self, approved origins and `blob:` for the
worker. A third-party tile request SHALL NOT be required to render the map in
an air-gapped deployment.

### Requirement: Accessible dialogs and i18n

All modals SHALL trap focus, close on Escape, restore focus and declare
`role="dialog" aria-modal="true"`, matching the command palette. All
user-facing strings in shipped views SHALL be routed through i18next for `en`
and `fa`; no raw English text SHALL remain in JSX.

### Requirement: Real diagnostics

Ops Health and Storage SHALL show measured values from the gateway or an
explicit "not instrumented" state; fabricated `ok:false` rows SHALL NOT be
presented as measurements. Effects and memos SHALL depend on stable
callbacks/values rather than whole-store objects during streaming. The
single-file build tradeoff SHALL be documented in an ADR.
