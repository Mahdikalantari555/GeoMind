## Context

The web app (`apps/web/`) already has a functional i18next setup with `en.json` and `fa.json` key trees, runtime language switching, and `<html dir>` manipulation. Several feature pages were built incrementally and never completed the i18n wrap — they still contain literal English strings. Additionally, one component uses a physical `ml-` Tailwind class that breaks when the document is RTL. This design covers how to close those gaps systematically.

See `proposal.md` for motivation. The existing web-app spec's "Bilingual RTL" requirement is the behavioural contract; this change makes it fully true.

## Goals / Non-Goals

**Goals:**
- Achieve 100% `t()` coverage for user-visible text in every feature-page component.
- Eliminate all physical directional Tailwind utilities in `apps/web/src/features/`.
- Keep `en.json` and `fa.json` key-tree parity.
- Preserve existing LTR appearance for English users (zero visual regression).

**Non-Goals:**
- Adding new languages beyond `en` and `fa`.
- Changing the i18next infrastructure (kept as-is; no migration needed).
- Updating server-side strings (out of scope; purely web-layer).
- Rewriting the eval or review APIs — only UI strings change.
- Fixing low-priority code smells (e.g. `set-state-in-effect` pattern in SettingsPage, dead conditional in `client.ts`) unless they block i18n correctness.

## Decisions

### D1: Where to add missing i18n keys
**Decision:** Add keys under new top-level namespaces (`eval`, `review`, `agent`, `doctor`, `ingest`, `ask`, `maps`, `farms`) in both `en.json` and `fa.json`, mirroring the existing flat structure (e.g. `nav.*`, `search.*`).

**Rationale:** The existing JSON files use a flat namespace-per-domain pattern. Introducing sub-namespaces only where needed keeps lookups simple and avoids restructuring the entire file. Persian translations are prepared by a human translator; automated translation of new keys is deferred to the implementation phase.

**Alternatives considered:**
- Deep nested namespaces (e.g. `pages.eval.*`): rejected — inconsistent with existing flat style.
- Single `strings.*` namespace: rejected — hurts discoverability and contradicts current organisation.

### D2: Hardcoded strings in option values and data labels
**Decision:** Strings that appear as `<option>` values (e.g. `"proposed"`, `"supported"`, `"verified"`, `"rejected"`) SHALL NOT be wrapped in `t()` if they are programmatic enum values consumed by the API. Only the *label* displayed to the user SHALL be translated. For inline data labels like `"class"` in MapsPage, wrap in `t()` and add a key.

**Rationale:** Mixing i18n keys with API-contract string values creates coupling between translation and backend expectations. Option values used as state filters must remain stable; only visible labels change.

**Alternatives considered:**
- Translate enum values too: rejected — would require every API consumer to understand translated strings.

### D3: Fixing the `ml-1.5` → `ms-1.5` change
**Decision:** Directly replace `ml-1.5` with `ms-1.5` in `SearchPage.tsx:329`. No other physical classes were found in the grep audit.

**Rationale:** Minimal, targeted fix. Tailwind's `ms-*` (margin-start) maps to `margin-inline-start`, which is `margin-left` in LTR and `margin-right` in RTL — exactly the desired behaviour.

**Alternatives considered:**
- Custom CSS variable for margin-start: rejected — over-engineered for a single occurrence.
- Leave as-is: rejected — breaks RTL layout for the modality chip.

### D4: How to verify key parity
**Decision:** During implementation, run a script that diffs the key paths of `en.json` vs `fa.json` and fails the build on any mismatch. For this planning phase, manually verify by tree-walking both files.

**Rationale:** Automated parity checking prevents future drift. A simple recursive key-diff is cheap to add and high-value.

## Risks / Trade-offs

- **[Risk]** Persian translations for new keys are not yet written → **Mitigation:** Add placeholder English-only keys first; add Persian equivalents in a follow-up task. The app falls back to English anyway, so no breakage.
- **[Risk]** Changing i18n keys may invalidate localStorage-stored language preference if key paths shift unexpectedly → **Mitigation:** This change only adds keys; no existing keys are renamed or removed.
- **[Risk]** `t()` calls with missing keys render the key path (e.g. `eval.runBenchmark`) in English → **Mitigation:** Fallback is `en`, so English users always see correct text; Persian users see English for new keys until translations land. Acceptable for a completion pass.

## Migration Plan

This is a client-side-only change with no server or database migration. Steps:

1. Add missing i18n keys to `en.json` first (safe — no visual change for anyone).
2. Add Persian translations to `fa.json` for the same keys.
3. Wrap JSX strings in each affected component with `t()`.
4. Replace `ml-1.5` → `ms-1.5` in `SearchPage.tsx`.
5. Run `pnpm lint && pnpm build` from `apps/web/` to confirm no type errors.
6. Run `pnpm test` to confirm unit tests pass.

**Rollback:** Revert the git commit. No data migration or config change to undo.

## Open Questions

(None — all decisions resolved. The low-priority `set-state-in-effect` pattern in `SettingsPage.tsx` and the dead conditional in `client.ts:11` are acknowledged but intentionally deferred per the Non-Goals list.)
