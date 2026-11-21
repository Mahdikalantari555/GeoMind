# Design

## Context

See `proposal.md` - Why. The web app uses React Router v6 with a single
`AppShell` + `Sidebar`. Design tokens live in `apps/web/src/index.css`
(oklch `--gf-*` variables, Tailwind v4 `@theme inline`). RTL is handled via
logical properties and i18n. No state management library beyond TanStack Query
and React Router. Existing tests: Vitest + Testing Library.

## Goals / Non-Goals

**Goals:**
- Make the 19 existing routes discoverable via 3 hubs + Simple/Advanced mode.
- Turn `/` into a Home dashboard that leads to a cited answer in 5 minutes.
- Provide consistent empty states, page headers, and loading skeletons.
- Add a keyboard-driven command palette.
- Preserve all routes, the gateway contract, and existing tests' expectations.

**Non-Goals:**
- No new backend endpoints or data-model changes.
- No visual rebrand beyond the existing `--gf-*` token system (existing-codebase
  mode: match, don't invent).
- No removal of routes; only visibility grouping.
- No mobile-specific layout (desktop-first, responsive down to 375px).

## Decisions

1. **State for mode + hub collapse in localStorage, not server.**
   Rationale: presentation preference is client-only; avoids gateway changes.
   Alternative: store in workspace settings — rejected (couples UI pref to data).

2. **Home dashboard replaces OverviewPage at `/`.**
   Rationale: `/` is the natural landing; reusing the route avoids redirect churn.
   The old raw-stats view moves to a "Workspace stats" disclosure on Home.

3. **Simple/Advanced as a boolean in localStorage (`gf.mode`).**
   Default Simple. Hub visibility filtered by mode; routes still reachable via
   command palette and direct URL in both modes (no hard gating).

4. **Command palette built on a small custom component (no new dep).**
   Rationale: avoid adding `cmdk` dependency; a dialog + filtered list is ~80 LOC.
   Alternative: `cmdk` — rejected to keep bundle small and match shadcn-less stack.

5. **PageHeader + EmptyState + Skeleton as shared components in
   `apps/web/src/components/`.**
   Rationale: single source of truth; tests can target stable testids.

6. **Empty-state CTAs are route-driven, not data-driven.**
   Each page owns its empty condition and CTA target; shared component only
   renders title/description/action.

7. **Recent activity on Home derived from existing TanStack Query caches
   (assets, collections, stats), not a new endpoint.**
   Rationale: no backend changes; "recent" = most recently updated items already
   in cache.

## UX & Accessibility Best Practices

The plan follows the existing-codebase design mode (match the `--gf-*` token
system, take zero unrequested visual risks) plus these concrete practices:

- **Information architecture:** 3 hubs + collapsible Workspace section; Simple
  mode shows 5 core pages; Advanced unlocks all. Direct URLs and the command
  palette always reach every page (no hard gating).
- **Progressive disclosure:** Home dashboard shows health cards + quick actions
  first; raw stats live behind a disclosure. Empty states guide the next action.
- **States coverage:** every page has loading (skeleton), empty (CTA), error
  (banner + retry), and success states — not just the happy path.
- **Accessibility:** keyboard-navigable command palette (arrows/Enter/Escape),
  visible focus rings (`focus-visible`), tap targets ≥ 44px, ARIA labels on
  icon-only buttons, `prefers-reduced-motion` guard on any animation.
- **Contrast:** body text ≥ 4.5:1, large display ≥ 3:1 against `--gf-bg`/`--gf-panel`.
- **RTL:** logical properties only (`ps/pe/ms/me`); layout smoke-checked in
  both directions at 375px.
- **Responsive:** mobile-first down to 375px; sidebar collapses to a drawer on
  small screens.
- **Typography:** reuse existing system stack (`system-ui` + `Vazirmatn`); no
  new web fonts.
- **Consistency:** shared `PageHeader`, `EmptyState`, `Skeleton` components as
  the single source of truth.

## Home Dashboard Wireframe

```
+------------------------------------------------------------------+
| GeoMind   [Workspace: ... v]          [health] [lang] [mode] [cmdk]|
+----------+-------------------------------------------------------+
|          |  +--------------------------------------------------+ |
| Home     |  | Hero: "Ask your data. Cited answers, no hallucination." | |
| Knowledge|  |  [ Ask a question -> ]  [ Ingest docs ]  [ Map ]      | |
|  Ask     |  +--------------------------------------------------+ |
|  Search  |  +------------------+  +-----------------------------+  |
|  Ingest  |  | Try in 5 min     |  | Recent activity             |  |
|  ...     |  | 1 Open sample    |  | - asset X ingested          |  |
| Geo      |  | 2 Ask "..."      |  | - run Y completed           |  |
|  Maps    |  | 3 See citation   |  | - feedback accepted         |  |
|  Farms   |  +------------------+  +-----------------------------+  |
| Agent    |  +--------------------------------------------------+ |
|  Chat    |  | Workspace health: collections 4 . assets 12 . seg 340 | |
|  ...     |  +--------------------------------------------------+ |
| Workspace|                                                        |
|  (coll.) |                                                        |
+----------+-------------------------------------------------------+
```

## Risks / Trade-offs

- [Risk] Simple mode hiding pages may frustrate power users → Mitigation: direct
  URLs and command palette still reach all pages; Advanced toggle one click away.
- [Risk] Empty-state logic duplicated across 19 pages → Mitigation: shared
  `EmptyState` component + a `useEmptyState` hook standardizing conditions.
- [Risk] RTL regressions when restructuring nav → Mitigation: logical
  properties only (`ps/pe/ms/me`), existing RTL smoke tests.
- [Risk] Home dashboard fetches multiple queries → Mitigation: reuse existing
  hooks; TanStack Query dedupes; skeleton fallback.

## Migration Plan

1. Add shared components (PageHeader, EmptyState, Skeleton, CommandPalette,
   ModeToggle) + tests.
2. Refactor Sidebar into hubs + Workspace section + mode filtering.
3. Replace OverviewPage with Home dashboard.
4. Add empty states to each page incrementally (one PR per hub).
5. Add command palette to AppShell.
6. Update i18n keys (en/fa).
7. Update Vitest tests and E2E smoke.

Rollback: revert the change; routes and API untouched, so no data migration.

## Open Questions

- Should the "Try in 5 minutes" sample workspace auto-create on first run, or
  require a click? (Deferrable; recommend click to avoid surprising file writes.)
- Should command palette include actions (e.g., "Ingest file") or only
  navigation? (Recommend navigation-only for v1.)