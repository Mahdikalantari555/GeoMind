# Tasks — studio-product-completion

Verification gates:
- `conda run -n geo pytest server/tests -q && conda run -n geo ruff check server`
- `cd apps/studio && pnpm.cmd check && pnpm.cmd test && pnpm.cmd build`

## 1. Landsat 8/9 unification (do first — touches AcquireView)

- [ ] 1.1 Replace the two Landsat options with one in `AcquireView.tsx:9`; keep
      `sensorKey -> "landsat"`; update `sample.ts` demo ids and i18n. (A-005)
- [ ] 1.2 Update `api.test.ts` mapping assertions. (A-005)

## 2. Custom provider + runtime key (A-001)

- [ ] 2.1 Admin-only `POST /providers` (name, HTTPS base, key slot) + gateway
      config store; extend `catalog()`; `/connect` resolves registered providers. (A-001)
- [ ] 2.2 Allow `custom` provider identity in settings/lib/factory; widen key-env
      allow-list to registered names, reject `PATH`. (A-001, S-008)
- [ ] 2.3 Password API-key input in `ProviderPicker` (state only); send
      `llm_api_key`; show configured flags; call `refreshLive()` after apply. (A-001)
- [ ] 2.4 Fetch catalog on mount with AbortController + empty/loading states;
      replace the private `request()` with typed `lib/api.ts` functions. (ARCH-01)
- [ ] 2.5 All provider strings via i18next `en`/`fa`. (DIR-06)

## 3. Scene previews + RGB bands (A-002, A-003)

- [ ] 3.1 Add `preview_url`/`assets` to `SceneRef`; populate from STAC in both
      search paths; thread through `scenes_from_rows`, schemas and `/data/search`. (A-002)
- [ ] 3.2 Add `GET /data/scenes/{id}/preview` proxy with approved-host/redirect
      policy and 404 fallback. (A-002)
- [ ] 3.3 Add `band_map` to `FetchResult`/job result; add multi-band composite
      tile route (`paths`, `bands`, stretch) with sandbox checks and 2/98 stretch. (A-003)
- [ ] 3.4 Studio: render `<img>` preview; add R/G/B selectors + presets +
      "Edit bands"; persist on `MapLayer`; per-layer tile error/retry. (A-002, A-003, G-034)
- [ ] 3.5 Gateway tests: preview field survives search; `bands=3,2,1` gives a
      3-channel PNG; out-of-sandbox path → 403. (T-080)

## 4. Agent/knowledge correctness

- [ ] 4.1 Remove zero-count citation stripping; strip once post-terminal. (CORRECT-02)
- [ ] 4.2 Request-generation guards for Ask/search; AbortSignal through
      `streamAgentChat`, abort on unmount/new send. (CORRECT-03, CORRECT-04)
- [ ] 4.3 Add `id`/`args` to SSE tool events; match end events by id. (CORRECT-05)
- [ ] 4.4 Abort previous workspace refresh; dedup key from `context.roi`. (CORRECT-06, CORRECT-07)

## 5. Shell, persistence, hardening

- [ ] 5.1 Persist thresholds via debounced `PUT /workspace/settings`; hydrate
      on refresh. (G-035)
- [ ] 5.2 Wire Ops to `/health` + doctor; remove fabricated rows. (F-100)
- [ ] 5.3 Proxy basemap/glyphs through gateway (or offline pack) + ADR; add CSP;
      singleton worker blob URL revoked on teardown. (S-016, S-017, CORRECT-10)
- [ ] 5.4 i18n audit; stable effect dependencies; shared accessible modal
      primitive; single-file build ADR. (DIR-06, PERF-01, PERF-02, CORRECT-09)
- [ ] 5.5 Remove the hardcoded `gatewayConfigured = true` flag in `lib/api.ts:11`
      and its unreachable branch; derive the state from the gateway probe. (ARCH-02)

## 6. Component-test harness and final gate

- [ ] 6.1 Add jsdom + @testing-library/react + vitest jsdom config. (T-078)
- [ ] 6.2 Tests: provider form (name/base/key, no localStorage write), scene
      preview `<img>`, band selectors change tile URL, citations survive
      streaming, Ask/search race guard, modal Escape/focus. (T-078, T-080)
- [ ] 6.3 Regenerate OpenAPI client; `pnpm.cmd check && pnpm.cmd test && pnpm.cmd build` green.
