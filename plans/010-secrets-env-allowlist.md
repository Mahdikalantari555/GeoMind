# Plan 010: Allow-list LLM key env-var names (runtime set + workspace secrets merge)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- server/src/geofront_api/routers/workspace.py server/src/geofront_api/routers/environment.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

The gateway intentionally keeps LLM API keys in `os.environ` (AGENTS.md
invariant 3 — set at runtime, never persisted to the workspace DB, never
returned). But two flows accept **arbitrary env-var names** from outside the
gateway and write them into the process environment:

1. `PUT /api/v1/workspace/settings` uses the request's `llm_api_key_env`
   verbatim as the target variable (`os.environ[key_env] = value`), so a
   request can overwrite `PATH`, `GEOFOND_WORKSPACE`, proxy vars, or other
   providers' credentials.
2. Opening a workspace merges **every** key of
   `<ws>/.geofront/secrets.json` into `os.environ` unvalidated — and
   workspaces are shareable project directories, so a workspace from another
   party can shadow environment variables before any request is handled.

The invariant covers "the key value goes to env", not "any env name is
writable". The fix mirrors the allow-list pattern the gateway already uses
for the setup wizard (`routers/environment.py`).

## Current state

- `server/src/geofront_api/routers/workspace.py:276-286` (PUT settings):
  ```python
  key_env = (
      raw.get("llm_api_key_env")
      or getattr(ws.settings, "llm_api_key_env", None)
      or "GEOMEMORY_LLM_API_KEY"
  )
  key_env = str(key_env).strip() or "GEOMEMORY_LLM_API_KEY"
  # Set in process env (runtime only, never returned)
  os.environ[key_env] = str(api_key_value)
  log.info("LLM API key set via settings for env var %s (value hidden)", key_env)
  ```
- `server/src/geofront_api/routers/workspace.py:85-90` (workspace open):
  ```python
  if getattr(ws.settings, "persist_secrets", False):
      secrets = _load_persisted_secrets(ws.path)
      for k, v in secrets.items():
          if k and v:
              os.environ[k] = v
  ```
- **The exemplar to copy** — `routers/environment.py:12-16,39-48`:
  ```python
  ALLOWED_ENV_VARS = {
      "HF_ENDPOINT": "Hugging Face hub endpoint used for model downloads",
      "GEOMEMORY_EMBEDDING_ROOT": "Shared embedding model cache root scanned by every workspace",
      "HF_HOME": "huggingface_hub home (defaults to ~/.cache/huggingface)",
  }
  ...
  for key, value in req.env.items():
      if key not in ALLOWED_ENV_VARS:
          ignored.append(key)
          continue
  ```
- `server/src/geofront_api/schemas.py:90` — `llm_api_key_env: str | None`
  (unconstrained). The lib field (`libs/geomemory/.../core/models.py:176`)
  is likewise unconstrained — out of scope here (server-side validation
  suffices; the lib is not to be touched in this plan).
- Existing default name appears as the string `"GEOMEMORY_LLM_API_KEY"` in
  `state.py:124`, `routers/doctor.py:263`, `workspace.py:281,283`, and the
  lib models — do NOT refactor those in this plan (that is a separate small
  cleanup); just keep using the same literal.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Server tests | `conda run -n geo pytest server/tests -q` | 156 passed baseline |
| Server lint | `conda run -n geo ruff check server` | exit 0 |
| Server typecheck | `cd server && conda run -n geo mypy --strict src/` | exit 0 |

## Scope

**In scope**:
- `server/src/geofront_api/routers/workspace.py` (both flows + helper)
- `server/src/geofront_api/schemas.py` (optional pattern validator on
  `llm_api_key_env` — only if it matches existing schema style)
- `server/tests/test_secrets_env_allowlist.py` (create)

**Out of scope**:
- `libs/geomemory/**` — the settings model stays permissive; the gateway is
  the enforcement point.
- The `persist_secrets` feature itself (whether it should exist is an owner
  decision recorded in the audit; here we only make it safe).
- The docs' invariant wording (`AGENTS.md` invariant 3 drift re
  `persist_secrets`) — separate docs change.

## Git workflow

- Branch: `advisor/010-secrets-env-allowlist`
- Commits: `fix(server): allow-list LLM key env-var names on settings PUT`, `fix(server): restrict workspace secrets.json merge to known key env vars`

## Steps

### Step 1: Add the validator helper

In `routers/workspace.py` (near `_secrets_path` / the other helpers):

```python
import re

# Env vars that may receive LLM credentials at runtime. The pattern bounds
# the *name*; values come from the request or secrets.json and are never
# logged or returned (AGENTS.md invariant 3).
_LLM_KEY_ENV_RE = re.compile(r"^GEOMEMORY_[A-Z0-9_]+$")

def _validate_key_env(name: str) -> str | None:
    """Return the validated env-var name, or None if not allow-listed."""
    name = (name or "").strip()
    return name if _LLM_KEY_ENV_RE.match(name) else None
```

### Step 2: Enforce on PUT settings

Replace the `os.environ[key_env] = ...` block so a non-conforming name is
rejected before any environment mutation:

```python
validated = _validate_key_env(key_env)
if validated is None:
    raise GeoFrontError(
        code="invalid_key_env",
        message=f"llm_api_key_env must match GEOMEMORY_[A-Z0-9_]+ (got {key_env!r}).",
        status_code=422,
    )
os.environ[validated] = str(api_key_value)
log.info("LLM API key set via settings for env var %s (value hidden)", validated)
```

Also use `validated` for the later `persist_secrets` write
(`cur[key_env] = ...` at workspace.py:308) so persistence and runtime agree.

**Verify**: `conda run -n geo pytest server/tests -q` → existing workspace settings tests pass.

### Step 3: Restrict the workspace-open secrets merge

Replace the merge loop in `_open_workspace_path`:

```python
if getattr(ws.settings, "persist_secrets", False):
    secrets = _load_persisted_secrets(ws.path)
    for k, v in secrets.items():
        validated = _validate_key_env(k)
        if validated is None:
            log.warning("secrets.json: ignoring non-conforming env var name %r", k)
            continue
        if v:
            os.environ[validated] = v
```

**Verify**: `conda run -n geo pytest server/tests -q` → workspace open tests pass.

### Step 4: Tests

Create `server/tests/test_secrets_env_allowlist.py`:

1. `PUT /api/v1/workspace/settings` with `{"llm_api_key": "sk-test",
   "llm_api_key_env": "PATH"}` → 422 `invalid_key_env`, and
   `os.environ["PATH"]` unchanged (capture before/after).
2. Same request with `"llm_api_key_env": "GEOMEMORY_LLM_API_KEY"` (or
   `GEOMEMORY_TEST_KEY` to avoid clobbering) → 200/202 per current
   contract; assert `os.environ["GEOMEMORY_TEST_KEY"] == "sk-test"`; clean
   up the var in the test (`os.environ.pop`).
3. Workspace-open merge: create a workspace dir with
   `.geofront/secrets.json` containing `{"GEOFOND_WORKSPACE": "/evil", "GEOMEMORY_TEST_KEY": "v"}`
   and `persist_secrets: true` in settings — after opening, assert
   `GEOMEMORY_TEST_KEY` set, `GEOFOND_WORKSPACE` NOT modified, and a
   warning logged (use caplog).
4. Empty-string key value: `llm_api_key: ""` → current behavior sets
   `os.environ[name] = ""` — keep that behavior (do not change semantics
   beyond name validation) and assert it.

Use the conftest workspace fixtures for steps 3-4; if creating a
`persist_secrets` workspace in tests is heavier than the existing fixtures
support (settings file format from `libs/geomemory/.../config.py:save_settings`),
an alternative is to test `_open_workspace_path` directly with a
monkeypatched `GeoMemory.open` returning a stub object carrying
`settings.persist_secrets=True` and `path=<tmp dir>` — choose whichever
matches existing test patterns with the least machinery.

**Verify**: `conda run -n geo pytest server/tests/test_secrets_env_allowlist.py -q` → all pass.

## Test plan

- New tests above; full server suite green (156+).
- lint + mypy clean.

## Done criteria

- [ ] `os.environ[` is never indexed with a non-validated name in
      `workspace.py` (`grep -n "os.environ" server/src/geofront_api/routers/workspace.py` — each write site is guarded by `_validate_key_env`)
- [ ] New tests pass; full server suite green
- [ ] `conda run -n geo ruff check server` → exit 0
- [ ] `cd server && conda run -n geo mypy --strict src/` → exit 0
- [ ] No lib changes; no other files touched
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any existing workspace (fixture or test) legitimately persists a
  secrets.json key that does NOT match `^GEOMEMORY_[A-Z0-9_]+$` and is
  required by a test — report the key name; the pattern may need widening
  with an owner decision.
- The settings PUT route has been restructured so `key_env` resolution
  differs from the excerpt — report.
- A test requires mutating real `PATH`/`GEOFOND_WORKSPACE` to pass — do not
  mutate global process env in tests; restructure the test instead.

## Maintenance notes

- If the owner later adds provider-specific keys (e.g. `QDRANT_API_KEY` via
  env), widen the pattern deliberately and document it in AGENTS.md
  invariant 3 — don't silently special-case names.
- The audit's SECURITY-08 (qdrant key echoed in settings responses +
  plaintext persistence) is a separate, still-open finding — not covered
  here.
- Reviewer should scrutinize: no behavior change for the default
  `GEOMEMORY_LLM_API_KEY` flow; the persist-secrets write path uses the
  validated name consistently.
