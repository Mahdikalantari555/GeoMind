# Tasks: design-system-instrument

- [ ] 1. Design Tokens & Typography
  - [ ] 1.1 Update `apps/web/src/index.css` with emerald/teal oklch tokens and dark mode counterparts.
  - [ ] 1.2 Add tabular mono classes and typography utilities in Tailwind theme.
- [ ] 2. Shell & Top Navigation
  - [ ] 2.1 Refactor `Sidebar.tsx` into a clean icon-rail with tooltips and badge support.
  - [ ] 2.2 Refactor `AppShell.tsx` header to include global search trigger input, status indicator, and workspace switcher.
- [ ] 3. Workspace Setup Modal (`KwzrE.jpg`)
  - [ ] 3.1 Create `WorkspaceModal.tsx` split component (list on left, form/demo on right).
  - [ ] 3.2 Wire workspace switching and demo workspace loader to API.
- [ ] 4. Dashboard & Sparkline Cards (`lQSVu.jpg`)
  - [ ] 4.1 Create reusable `Sparkline.tsx` SVG component.
  - [ ] 4.2 Create `MetricCard.tsx` with value, unit, delta pill, and sparkline.
  - [ ] 4.3 Update `OverviewPage.tsx` to match the `lQSVu.jpg` dashboard layout.
- [ ] 5. Verification & Tests
  - [ ] 5.1 Add component unit tests for `MetricCard` and `WorkspaceModal`.
  - [ ] 5.2 Verify RTL layout in Persian (`fa`).
  - [ ] 5.3 Run `pnpm build` and `pnpm test`.
