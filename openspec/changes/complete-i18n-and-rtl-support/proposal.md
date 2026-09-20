## Why

The web UI has two classes of i18n/RTL defects that prevent Persian users from having a correct experience: some pages still render hardcoded English strings instead of using the i18next translation system, and at least one component uses a physical (`ml-`) Tailwind class instead of a logical (`ms-`) one, breaking RTL layout. The existing web-app spec declares a "Bilingual RTL" requirement but the implementation is incomplete — these gaps must be closed before any further feature work is trusted on the RTL surface.

## What Changes

- Wrap every remaining user-visible English string in `apps/web/src/features/**` in `t()` calls and add the corresponding keys to `en.json` and `fa.json`.
- Replace the single non-logical Tailwind RTL property (`ml-1.5` → `ms-1.5`) in `SearchPage.tsx`.
- Audit every page component against the `en.json` / `fa.json` key tree to confirm zero untranslated strings remain.
- Add `eval` and `review` sections to both i18n JSON files covering all new keys introduced by this change.

## Capabilities

### New Capabilities
- `i18n-completion`: Complete end-to-end i18n coverage for all web feature pages — every visible string SHALL come through `t()`, and en/fa JSON key trees SHALL remain in sync after every edit.
- `rtl-property-correctness`: All layout-relevant Tailwind spacing classes in feature pages SHALL use logical properties (`ms/pe/me/ps`) instead of physical ones (`ml/mr/pl/pr`), so layout mirrors correctly under RTL.

### Modified Capabilities
- `web-app`: The "Bilingual RTL" requirement SHALL be upgraded from partial (some pages covered) to full (all pages covered). Every scenario it currently lists SHALL continue to pass with the expanded set of translated pages and corrected logical properties.

## Impact

- `apps/web/src/features/` — all feature page components (eval, feedback/review, overview, agent-chat, doctor, ingest, ask, maps, farms).
- `apps/web/src/i18n/en.json` and `apps/web/src/i18n/fa.json` — new keys added under `eval`, `review`, `overview`, `agent`, `doctor`, `ingest`, `ask`, `maps`, `farms`.
- No server or lib changes — purely web-layer UI work.
- No API contract change; only client-side rendering changes.
- Backward compatible: existing English-speaking users see no behavior change; Persian users gain missing translations.
