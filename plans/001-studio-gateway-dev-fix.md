# Plan 001: Make Studio's live-gateway mode reachable in dev

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- apps/studio/src/lib/api.ts apps/studio/vite.config.ts server/src/geofront_api/main.py`
> If any of those files changed since commit `2b85a31`, compare the "Current
> state" excerpts below against the live code; on mismatch treat it as a
> STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

GeoMind Studio (`apps/studio`, the primary product front) has two independent
defects that make its **live gateway mode unreachable in development**:

1. `API_BASE` is only populated from `VITE_GEOMIND_API`. When that env var is
   unset (the default after `pnpm dev`), every API helper short-circuits to
   demo/offline mode. The vite dev-server proxy for `/api → :8000`
   (`vite.config.ts:21-26`) is dead config — no code path ever emits a
   relative `/api` request.
2. Even when a developer sets `VITE_GEOMIND_API=http://localhost:8000`, the
   gateway's CORS allow-list (`DEV_ORIGINS`) only permits port **5173**
   (legacy `apps/web`), while studio dev runs on **5174** — so every
   fetch/EventSource from studio is blocked by CORS before it reaches a
   handler.

Net effect: the feature recently shipped in commit `2d4b6fa` ("wire real
gateway routes") cannot actually be exercised against a running gateway
without reading source code. This plan also unblocks studio test/e2e work.

## Current state

- `apps/studio/src/lib/api.ts` — API helpers; base URL + demo gating live here.
  ```ts
  // api.ts:4
  export const API_BASE: string | undefined = (import.meta.env.VITE_GEOMIND_API as string | undefined)?.replace(/\/$/, "");
  // api.ts:7
  export const DEMO_MODE: boolean = (import.meta.env.VITE_GEOMIND_DEMO as string | undefined) === "1";
  // api.ts:9
  export const gatewayConfigured = Boolean(API_BASE);
  // api.ts:15-16
  export async function probeGateway(): Promise<boolean> {
    if (!API_BASE) return (gatewayUp = false);
  ```
  All request URLs are built as `${API_BASE}/api/v1/...` (absolute). Example:
  `api.ts:20` probe uses `fetch(\`${API_BASE}/api/v1/health\`)`.
- `apps/studio/vite.config.ts:19-27` — dev server on port 5174 with a proxy:
  ```ts
  server: {
    port: 5174,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  ```
- `server/src/geofront_api/main.py:66-69`:
  ```python
  DEV_ORIGINS = [
      "http://localhost:5173",
      "http://127.0.0.1:5173",
  ]
  ```
  (These feed FastAPI `CORSMiddleware` — find the `add_middleware` call in
  `main.py` and confirm it uses `DEV_ORIGINS` before editing.)
- Exemplar of the working relative-base pattern in the frozen legacy app:
  `apps/web/src/api/ops.ts:1` uses a relative `/api` base and the same vite
  proxy approach — match that behavior, not its code style (studio has its
  own style in `api.ts`).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Studio typecheck | `cd apps/studio && pnpm.cmd check` | exit 0 |
| Studio unit tests | `cd apps/studio && pnpm.cmd test` | 11 existing tests pass |
| Server tests | `conda run -n geo pytest server/tests -q` | 156 passed |
| Server lint | `conda run -n geo ruff check server` | exit 0 |

**Windows note:** use `pnpm.cmd`, never `pnpm` (the shim in `~/.bun/bin` is
broken on this machine). Python always runs via `conda run -n geo`.

## Scope

**In scope** (the only files you should modify):
- `apps/studio/src/lib/api.ts`
- `apps/studio/src/lib/api.test.ts` (extend)
- `apps/studio/.env.example` (create)
- `server/src/geofront_api/main.py` (DEV_ORIGINS only)
- `server/tests/test_cors_origins.py` (create)
- `README.md` line 54 and `AGENTS.md` studio lines (doc corrections only if
  they describe the proxy behavior; keep edits minimal)

**Out of scope** (do NOT touch):
- `apps/web/**` — frozen legacy app.
- The gateway's route handlers — CORS config only.
- `vite.config.ts` — the proxy is correct already; leave it.
- Demo mode semantics — `VITE_GEOMIND_DEMO=1` must keep working exactly as
  today (opt-in only).

## Git workflow

- Branch: `advisor/001-studio-gateway-dev-fix`
- Conventional commits, one concern per commit, e.g.:
  `fix(studio): default API base to relative /api so the dev proxy works`
  `fix(server): allow studio dev origin :5174 in CORS`
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add the studio dev origin to the gateway CORS allow-list

In `server/src/geofront_api/main.py`, extend `DEV_ORIGINS` to:

```python
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
```

**Verify**: `conda run -n geo pytest server/tests -q` → 156 passed.

### Step 2: Add a regression test pinning the origins

Create `server/tests/test_cors_origins.py` (look at any existing
`server/tests/test_*.py` for the import style — they import `from geofront_api.main import ...`):

```python
from geofront_api.main import DEV_ORIGINS

def test_studio_dev_origin_allowed():
    assert "http://localhost:5174" in DEV_ORIGINS
    assert "http://127.0.0.1:5174" in DEV_ORIGINS
```

**Verify**: `conda run -n geo pytest server/tests/test_cors_origins.py -q` → 1 passed.

### Step 3: Make studio's API base fall back to relative `/api`

In `apps/studio/src/lib/api.ts` change the base resolution so that, when
`VITE_GEOMIND_API` is unset, the app uses relative paths (served by the vite
proxy in dev, and by the gateway in any same-origin deployment):

```ts
// "" (relative) when unset — the vite dev proxy serves /api → :8000,
// and same-origin deployments serve /api directly.
export const API_BASE: string =
  ((import.meta.env.VITE_GEOMIND_API as string | undefined)?.replace(/\/$/, "")) ?? "";
export const gatewayConfigured = true;
```

Then audit every URL construction in the file: all existing
`${API_BASE}/api/v1/...` templates already concatenate fine with an empty
string (they become `/api/v1/...`). Confirm no site does
`API_BASE + "/api/..."` in a way that would double-slash when empty
(`API_BASE` is `""`, so `/api/...` is already correct). Also check
`tileUrlFor` (`api.ts:162-165`): its `if (!API_BASE) return undefined;`
guard must be removed or changed to `if (!gatewayUp) return undefined;` so
tile URLs work through the relative base. `probeGateway` no longer needs its
`if (!API_BASE) return false` early exit — delete that line so the probe
always runs against the (relative) health endpoint.

Behavior contract after this change:
- Dev (`pnpm dev`, gateway on :8000): probe succeeds → online mode through
  the proxy. **This is the bug being fixed.**
- Dev without a gateway: probe fails → offline UI state (by design; NOT a
  crash, per the repo's abstention-state principle).
- Explicit `VITE_GEOMIND_API=http://host:port` still overrides the base.
- Demo mode unchanged: `VITE_GEOMIND_DEMO=1` gates sample data as before.

**Verify**: `cd apps/studio && pnpm.cmd check` → exit 0.

### Step 4: Extend studio tests for the new default

In `apps/studio/src/lib/api.test.ts`, follow the existing test style in that
file and add cases:

- `API_BASE` defaults to `""` when `VITE_GEOMIND_API` is unset.
- `gatewayConfigured` is `true` regardless of the env var.
- (If the file stubs `fetch` for `probeGateway` already, add: probe hits
  `/api/v1/health` — a relative URL — and returns `true` when the response
  is ok.)

**Verify**: `cd apps/studio && pnpm.cmd test` → existing 11 + new tests pass.

### Step 5: Document the env vars

Create `apps/studio/.env.example`:

```
# Absolute gateway base. Leave unset in dev — the vite proxy serves /api → :8000.
#VITE_GEOMIND_API=http://localhost:8000
# Opt-in demo data. Never a silent fallback.
#VITE_GEOMIND_DEMO=1
```

**Verify**: file exists; no other doc edits needed if README:54 and
AGENTS.md already say ":5174 proxies /api → :8000" (they do — that claim is
now true).

## Test plan

- New: `server/tests/test_cors_origins.py` (origins pinned).
- New: api.test.ts cases (base default, probe via relative URL).
- Structural pattern for studio tests: the existing `api.test.ts` file.
- Verification: commands in the table above, all green.

## Done criteria

- [ ] `conda run -n geo pytest server/tests -q` → 157 passed (156 + 1 new)
- [ ] `conda run -n geo ruff check server` → exit 0
- [ ] `cd apps/studio && pnpm.cmd check` → exit 0
- [ ] `cd apps/studio && pnpm.cmd test` → all pass including ≥2 new tests
- [ ] `apps/studio/.env.example` exists
- [ ] No files outside the in-scope list are modified (`git status`)

## STOP conditions

Stop and report back (do not improvise) if:
- `main.py` no longer contains a `DEV_ORIGINS` list or feeds CORS from it
  differently than described (drift).
- Step 3 reveals URL templates that break with an empty `API_BASE` in a way
  a mechanical `API_BASE ?? ""` doesn't fix (more than a trivial guard
  change).
- Any existing studio test asserts `gatewayConfigured === false` when the
  env var is unset — report; that expectation needs an owner decision
  before flipping it.

## Maintenance notes

- When studio e2e tests (Playwright) are added later, they should rely on
  this relative-base behavior against the dev proxy.
- If studio ever gets deployed standalone (single-file build opened without
  a same-origin gateway), `API_BASE` must then be set explicitly via
  `VITE_GEOMIND_API` — `.env.example` documents this.
- Reviewer should scrutinize: no leftover `if (!API_BASE)` guards that
  silently disable features in the default (relative) configuration.
