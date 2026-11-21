# Proposal — add-studio-first-run-workspace

## Why

Studio (the product front) violates the existing `first-run-setup` capability:
it never offers workspace create/open, so a fresh gateway leaves the user in a
broken first run — a drawn ROI is added to the store, the `POST /rois` sync
fails with `workspace_not_open`, and `addRoi` silently rolls it back. The user
sees their ROI vanish ("ترسیم شد ولی چیزی ذخیره/نمایش نمی‌شه"). Verified live
on 2026-11-19: gateway with closed workspace → ROI disappears after save with
no recovery path in the UI. The gateway API (`POST /workspace/create`,
`POST /workspace/open`, `GET /workspace/suggestions`) already exists and
`apps/web` conforms; Studio must too, because it is the primary application.

## What Changes

- Studio gains a first-run workspace flow conforming to the `first-run-setup`
  capability: when the gateway reports the workspace closed, Studio shows a
  blocking setup dialog with **Create new** (name only; optional explicit
  path) and **Open existing** (path + suggestions from
  `GET /workspace/suggestions`) — no dismissal without an open workspace.
- The Topbar workspace selector becomes functional: shows the active
  workspace name when open; offers create/open entry points when closed.
- The ROI save path fails with a clear, actionable message ("create a
  workspace first") instead of a generic error string.
- Studio refreshes workspace state from the `workspace_changed` SSE event so
  create/close outside the dialog keep the UI consistent.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `first-run-setup`: clarify that the Studio application (product front) is
  in scope and conforms: blocking first-run dialog, functional workspace
  selector, workspace-state refresh from `workspace_changed` events, and
  actionable failure for operations that require an open workspace. The
  gateway contract is unchanged (no server changes).
