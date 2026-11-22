# Proposal: studio-product-completion

> Large Studio + gateway change. Root `openspec/changes/`. Merges the four
> Studio-side audit tranches so one executor can deliver a coherent product UI.

## Why

The user reported two bugs that summarise Studio's product-readiness gap:
(1) Settings offers only OpenAI/OpenRouter and has no API-key field; (2) real
scene previews never show and there is no way to change bands after download.
Both were confirmed at `673908a`. The surrounding audit found the same pattern
elsewhere: citation markers are stripped from healthy streamed answers, Ask and
search race, chat is never cancelled on unmount, tool events match by name,
thresholds are local-only, Ops panels are fabricated, basemaps call third
parties (contradicting the data-sovereign promise), there is no CSP, and there
are **zero component tests**. Landsat 8/9 are also presented as two options
even though the backend and the external MCP STAC server already use one
`landsat-c2-l2` collection.

This change completes Studio as the product front in one pass: provider
configuration, scene acquisition visuals, the agent/knowledge correctness
fixes, accessibility/i18n/hardening, and a component-test harness.

## What Changes

**Provider configuration (A-001):**
- Admin-only `POST /providers` registers a named custom provider (name, HTTPS
  base URL, key slot); `catalog()` includes it; `/providers/connect` resolves
  registered providers instead of returning an opaque 422. Keep the SSRF /
  credential-exfiltration guard (`_valid_base`, fresh key slot per URL).
- Allow a distinct `custom` provider identity through settings and the backend
  factory; widen `llm_api_key_env` to registered provider env names while still
  rejecting `PATH`. Add a password API-key input to `ProviderPicker` (state
  only, never localStorage/logs) wired to `llm_api_key`; show configured flags
  and call `refreshLive()` after apply. Fetch the catalog on mount with empty/
  loading states and use the shared typed API client.

**Scene acquisition (A-002, A-003, A-005):**
- Add optional `preview_url`/`assets` to `SceneRef`, populate from STAC
  `rendered_preview`, thread through `/data/search` and the Studio DTO. Add a
  gateway preview proxy (approved hosts, no credentials, no redirect to an
  unapproved host). Studio renders a real `<img>` with a labelled synthetic
  fallback only in demo mode.
- Persist `band_map` in the download result; add a multi-band composite tile
  route that stacks named single-band files into an RGB VRT with per-channel
  stretch; keep `/data/tiles` unchanged. Add R/G/B selectors + per-sensor
  presets and an "Edit bands" action; persist the triple on `MapLayer`. Track
  tile errors per source id with a per-layer retry.
- Replace the two Landsat options with one "Landsat 8/9 (Collection 2 L2)"
  option (backend already unified; no dedupe needed).

**Agent, knowledge and shell correctness (the rest):**
- Never strip citations against a zero count; strip once after the terminal
  event. Add request-generation/AbortController guards to Ask, search and
  chat; add call id/args to SSE tool events and match by id.
- Build dedup keys from the captured ROI; persist thresholds; wire Ops to real
  health/doctor data; proxy basemap/glyph requests or ship offline tiles + ADR;
  add CSP; make the worker blob URL a singleton revoked on teardown.
- Move all strings into i18next (en/fa); depend on stable store callbacks;
  extract a shared accessible modal primitive; document the single-file build
  tradeoff in an ADR.
- Add jsdom + Testing Library and component tests covering both reported bugs
  plus the citation/race/modal regressions.

## Capabilities

### New Capabilities
- `provider-management` — admin-governed custom provider registration + runtime key.

### Modified Capabilities
- `gateway-scene-data` — preview metadata, preview proxy, `band_map`, composite tiles.
- `studio-acquire` — real quicklooks, RGB band picker, one Landsat 8/9 option.
- `studio-agent-rail` — preserved citations, cancellable streams, tool-call identity.
- `studio-ask` — request-generation guard.
- `studio-shell` — i18n, persistence, CSP, sovereign basemaps, accessible dialogs, diagnostics.

## Impact

- **Server:** `providers.py`, `schemas.py`, `workspace.py`, `data.py`,
  `scene_download.py`, `services/agent.py`; OpenAPI regenerated.
- **Studio:** most views/components/lib files; new dev deps (jsdom, Testing Library).
- **data_engine:** additive `SceneRef` fields only (the heavier fetch/Sentinel-1
  work lives in `sentinel1-and-scene-fetch`).

## Dependencies

- `product-hardening-and-trust` lands first: auth token transport, configured-
  flag responses, input sandbox and the SSE tool-event field all come from it.
- `unify-landsat` work should be the first step inside this change (it touches
  `AcquireView` before the preview/band work).
- Builds on the existing `studio-provider-library`, `add-studio-knowledge-agent`
  and `integrate-studio-frontend` changes rather than reopening them.

## Out of Scope

- Implementing the scripted-to-live chat replacement (F-095 / existing
  `add-studio-knowledge-agent` direction) beyond the correctness fixes above.
- Reversing `viteSingleFile()` (document only) or shipping offline tile packs
  (choose the gateway proxy path in this change; the pack is a follow-up).
- Per-user credential isolation.

## Findings covered

A-001, A-002, A-003, A-005, S-008, S-016, S-017, G-034, G-035, T-078, T-080,
CORRECT-01…12 (Studio), DIR-02…06, ARCH-01/02, PERF-01/02, F-100,
server CORRECTNESS-01…04, data_engine CORRECTNESS-01/02.
