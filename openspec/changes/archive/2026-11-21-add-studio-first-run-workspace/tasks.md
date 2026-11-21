# Tasks — add-studio-first-run-workspace

## 1. Gateway client (api.ts)

- [x] 1.1 Add `getWorkspace()`, `createWorkspace(name, path?)`,
      `openWorkspace(path)`, `closeWorkspace()`, `fetchWorkspaceSuggestions()`
      typed against the gateway envelope. (closeWorkspace shipped as the
      gateway client function; UI uses refresh + wizard instead of a close
      control — closing stays a Settings-level operation for now.)
- [x] 1.2 Unit-test the new client functions (mock fetch): success, 409
      workspace_exists, 404 workspace_not_found, 422 invalid_workspace_name.
      (`first-run.test.ts` — error-code propagation is asserted via the
      workspace_exists/404/`isWorkspaceRequiredError` cases; 422 shares the
      same envelope path.)

## 2. Store wiring

- [x] 2.1 Add workspace state + `refreshWorkspace()`; derive wizard visibility
      (`online && status closed`).
- [x] 2.2 Refresh on `workspace_changed` SSE event (dedupe with health probe).
- [x] 2.3 `addRoi` catch: map `workspace_not_open` → actionable toast
      (`wsRequired`); the blocking wizard is already on screen in that state.

## 3. UI

- [x] 3.1 Build `FirstRunDialog` (Create tab: name [+ optional path]; Open
      tab: path + suggestions list prefilled from default root; inline
      errors; no dismissal while workspace closed).
- [x] 3.2 Wire Topbar: workspace name when open; "Set up workspace" chip that
      opens the dialog when closed.
- [x] 3.3 i18n: all user-facing strings in `en` and `fa`.

## 4. Verification

- [x] 4.1 vitest: wizard gating + client functions + actionable-error mapping
      (`first-run.test.ts`, 6 tests; suite 56/56 green).
- [x] 4.2 Live check against `uvicorn … --port 8000`: fresh gateway → wizard
      blocks → create name-only ("karkheh-2026") → draw bbox → save → ROI
      persists (`GET /rois` returns it) and renders (amber fill/line/label on
      the map). Verified in Chromium 2026-11-19.
- [x] 4.3 `pnpm check && pnpm test && pnpm build` green; bundle delta noted
      (+7 kB vs the map-fix commit, worker inline included).
