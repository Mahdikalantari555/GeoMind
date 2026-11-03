# Tasks

## 1. Shared presentation components

- [x] 1.1 Create `PageHeader` component in `apps/web/src/components/PageHeader.tsx` with title/subtitle/action props and a stable testid; verify a unit test renders title.
- [x] 1.2 Create `EmptyState` component in `apps/web/src/components/EmptyState.tsx` with title/description/action props; verify unit test renders CTA.
- [x] 1.3 Create `Skeleton` loading placeholder component; verify unit test renders.
- [x] 1.4 Create `ModeToggle` component persisting `gf.mode` in localStorage; verify unit test toggles and persists.
- [x] 1.5 Add Vitest unit tests for the four components above and verify `pnpm test` passes.

## 2. Sidebar restructure into 3 hubs

- [x] 2.1 Refactor `Sidebar.tsx` GROUPS into Knowledge/Geo/Agent hubs + collapsible Workspace section; verify sidebar renders 3 hub headers.
- [x] 2.2 Filter sidebar items by Simple/Advanced mode (Simple shows Home, Ask, Search, Ingest, Map); verify Simple mode hides Agent hub items.
- [x] 2.3 Persist hub collapsed state in localStorage and verify collapse toggles.
- [x] 2.4 Add i18n keys for hub labels in en/fa and verify no missing-key warnings.

## 3. Home dashboard

- [x] 3.1 Replace `OverviewPage` with Home dashboard layout (hero CTA, quick actions, health cards, guided path); verify `/` renders hero.
- [x] 3.2 Remove raw JSON stats from default view (move to collapsible disclosure); verify no `<pre>` stats in initial render.
- [x] 3.3 Implement "Try in 5 minutes" three-step guided path with links; verify each step links to target route.
- [x] 3.4 Add recent activity from existing query caches; verify renders without new endpoint.

## 4. Empty states per page

- [x] 4.1 Add EmptyState to Assets, Collections, Index pages; verify empty state shows CTA when no data.
- [x] 4.2 Add EmptyState to Maps, Farms pages; verify empty state shows CTA.
- [x] 4.3 Add EmptyState to Agent pages (chat, conversations, playbooks); verify empty state shows CTA.
- [x] 4.4 Add EmptyState to Search, Ask, Feedback, Eval pages; verify empty state shows CTA.

## 5. Command palette

- [x] 5.1 Create `CommandPalette` component triggered by Ctrl/Cmd+K with page list; verify opens on shortcut.
- [x] 5.2 Implement keyboard navigation (arrows, Enter, Escape) and navigation on select; verify unit test.
- [x] 5.3 Mount CommandPalette in AppShell and verify shortcut works app-wide.

## 6. Page headers and loading states

- [x] 6.1 Adopt PageHeader on all 19 pages; verify each page renders a title.
- [x] 6.2 Add Skeleton placeholders to pages with async data; verify loading state shows skeleton.

## 7. i18n and RTL

- [x] 7.1 Add all new i18n keys to en.json and fa.json; verify `pnpm test` i18n tests pass.
- [x] 7.2 Smoke-check layout in both LTR and RTL at 375px; verify no horizontal overflow.

## 8. Tests and integration

- [x] 8.1 Update Vitest tests for new components and navigation; verify `pnpm test` passes.
- [ ] 8.2 Update Playwright E2E smoke for new home dashboard and nav; verify E2E passes against live gateway.
- [x] 8.3 Run `pnpm lint && pnpm build && pnpm test` and verify all green.
