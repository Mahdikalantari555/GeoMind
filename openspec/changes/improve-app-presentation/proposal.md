# Proposal

## Why

GeoMind already implements a full feature set (search, grounded ask, ingest,
index, feedback, eval, agent, maps, farms), but the web app presents them as a
flat list of 19 routes in a sidebar. A new end user cannot tell where to start,
the Overview page dumps raw JSON stats, and empty states are minimal. The result
is that the implemented value is hard to discover and the first-run experience
feels unfinished. This change reorganizes the presentation layer so the
existing capabilities are discoverable and the first 5 minutes lead to a cited
answer.

## What Changes

- Replace the raw-stats Overview with a **Home dashboard**: hero call-to-action
  ("Ask your data"), quick actions (Ask, Ingest, Map), a "Try in 5 minutes"
  guided path using bundled sample data, recent activity, and workspace health
  cards (no raw JSON).
- Restructure the sidebar from 4 groups of 19 links into **3 hubs** (Knowledge,
  Geo, Agent) plus a collapsible Workspace section, reducing visual clutter.
- Add a **Simple / Advanced mode** toggle (default Simple) exposing ~5 core
  pages in Simple mode and all pages in Advanced mode.
- Add designed **empty states** with CTAs on every page (no workspace, no
  assets, no collections, no farms).
- Add a **command palette** (Ctrl/Cmd+K) to jump to any page or recent item.
- Add a consistent **page header** component (title, subtitle, primary action)
  and skeleton loading states across pages.
- Keep all existing routes and the gateway contract unchanged (no breaking API
  changes).

## Capabilities

### New Capabilities
- `app-presentation`: home dashboard, hub-based navigation, simple/advanced
  mode, empty-state design, command palette, consistent page headers.

### Modified Capabilities
- `web-app`: presentation/IA requirements (navigation grouping, home
  dashboard, empty states, mode toggle) change at spec level.

## Impact

- Affected code: `apps/web/src/app/Sidebar.tsx`, `apps/web/src/app/AppShell.tsx`,
  `apps/web/src/features/workspace/OverviewPage.tsx` (becomes Home), new
  components under `apps/web/src/components/` (PageHeader, EmptyState,
  CommandPalette, ModeToggle).
- i18n: new keys in `en.json` / `fa.json` for hub labels, empty states,
  onboarding steps.
- No gateway/server changes; no API or DB changes. Tests: Vitest unit tests for
  new components; existing E2E smoke updated to new nav.