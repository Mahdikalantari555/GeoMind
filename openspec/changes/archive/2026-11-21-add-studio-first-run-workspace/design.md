# Design — add-studio-first-run-workspace

## Context

- Gateway contract already exists and is tested: `POST /api/v1/workspace/create`
  (`{name, path?, language?, offline?}`; empty path → default root),
  `POST /api/v1/workspace/open` (`{path}` — workspace dir or a parent holding
  exactly one workspace), `GET /api/v1/workspace/suggestions` (existing
  workspaces under the default root), `GET /api/v1/workspace` (status/path/
  settings), `POST /api/v1/workspace/close`, SSE event `workspace_changed`.
- `apps/web` implements the wizard already (frozen reference) — Studio reuses
  the same contract, not the same code (different design system).
- Studio store (`apps/studio/src/lib/store.tsx`) tracks `online` +
  workspace-ish state via `/health`; `api.ts` has `getHealth()` returning
  `workspaceOpen`. The Topbar workspace combobox is hard-disabled.
- `addRoi` (store.tsx:381) optimistically adds then rolls back when
  `createRoiRemote` rejects with the gateway's error envelope.

## Approach

1. **api.ts**: add `getWorkspace()` (status/path/name), `createWorkspace(name,
   path?)`, `openWorkspace(path)`, `closeWorkspace()`,
   `fetchWorkspaceSuggestions()`. Errors surface the gateway envelope's
   `message` (existing `ApiError` path).
2. **store.tsx**: hold `workspace: {status, path, name} | null`; a
   `refreshWorkspace()` action; the SSE `workspace_changed` listener calls it.
   Wizard open-state derives from `online && workspace?.status === "closed"`.
3. **FirstRunDialog** (new component): modal per the spec — Create tab
   (name required, optional path) and Open tab (path + clickable suggestions,
   prefilled default root). No outside-click/Escape dismissal when a workspace
   is closed. On success: toast + refresh workspace state.
4. **Topbar**: render `workspace.name` when open; when closed show an explicit
   "Set up workspace" chip that opens the dialog (the blocking dialog already
   covers first run; the chip covers reopening it deliberately).
5. **Save-ROI guard**: in `addRoi`'s catch, when the envelope code is
   `workspace_not_open`, toast the actionable message + a "Set up workspace"
   action opening the dialog (rollback behavior itself is already correct).
6. **Offline/demo mode**: the wizard is online-only (demo mode fabricates its
   workspace; `VITE_GEOMIND_DEMO=1` unchanged).

## Risks / Trade-offs

- The blocking wizard can annoy during local dev with a closed gateway —
  accepted: it matches the capability and the gateway defaults to creating
  under a default root, so one field + one click.
- Bundle: dialog is small; no new dependency (reuses existing ui.tsx widgets).

## Open Questions

(none — behavior pinned by the existing capability spec)
