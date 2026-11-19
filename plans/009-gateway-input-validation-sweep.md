# Plan 009: Gateway input-validation sweep (filenames, playbook names, export dir, workspace name)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- server/src/geofront_api/routers/ingest.py server/src/geofront_api/routers/agent/playbooks.py server/src/geofront_api/routers/feedback.py server/src/geofront_api/routers/workspace.py server/src/geofront_api/schemas.py`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: security (defensive hardening) + bug
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

Four gateway routes join client-controlled strings into filesystem paths or
directories without validation. Today (localhost single-user) they are
foot-guns; the moment the gateway is reachable beyond loopback
(docker-compose publishes `8000:8000` today) they become file-write and
file-read primitives. One sweep fixes all four with shared helpers and
tests. Two smaller error-contract violations ride along (`/asset` returning
500s where `/ingest/bytes` returns 422s for the same bad payload).

## Current state

- **9a — upload filename joined raw** (`routers/ingest.py:80-83`):
  ```python
  with tempfile.TemporaryDirectory(prefix="gf-ingest-") as tmp:
      target = Path(tmp) / filename
      target.write_bytes(data)
  ```
  `filename` comes from the multipart upload (`ingest.py:127-130`), the JSON
  body (`ingest.py:170-180`), or `IngestBytesRequest.filename`
  (`schemas.py:43-49`, length-constrained only). Only `_check_extension`
  (`ingest.py:46-55`) runs — it inspects the suffix. An absolute path or
  `../`-bearing name escapes the temp dir.
- **9b — playbook name into a path** (`routers/agent/playbooks.py:63`):
  ```python
  target = service.settings.workspace / "playbooks" / f"{name.replace('-', '_')}.md"
  ```
  (`name` is a URL path param; no charset check) and the save route
  (`playbooks.py:136-150`) passes `req.name` into
  `geoagent.playbooks.save_playbook` (`libs/geoagent/src/geoagent/playbooks.py:282-288`)
  which builds a write path from the caller-supplied name.
- **9c — feedback export to any directory** (`routers/feedback.py:141-158`):
  ```python
  @router.get("/export")
  async def export_feedback(task_type: str, output_dir: str | None = None) -> FileResponse:
      ws = get_state().require_workspace()
      out = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
      out.mkdir(parents=True, exist_ok=True)
  ```
- **9d — workspace name "sanitization" is only `.strip()`**
  (`routers/workspace.py:116-121`):
  ```python
  # sanitize workspace name for filesystem (allow letters, digits, - _)
  safe_name = req.name.strip() or "GeoMemory Workspace"
  target = base / safe_name if base.name != safe_name else base
  target.mkdir(parents=True, exist_ok=True)
  ```
  The comment promises a charset the code doesn't enforce; `..`, `/`, or a
  Windows drive prefix in `req.name` creates directories outside `base`.
- **9e — `/asset` JSON path 500s on bad input** (`routers/ingest.py:167,176`):
  `body = await request.json()` unguarded, and
  `base64.b64decode(body["data_base64"])` without `validate=True`/error
  handling — compare the sibling route `ingest.py:137-142` which maps the
  same failures to 422 `invalid_base64`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Server tests | `conda run -n geo pytest server/tests -q` | 156 passed baseline |
| Server lint | `conda run -n geo ruff check server` | exit 0 |
| Server typecheck | `cd server && conda run -n geo mypy --strict src/` | exit 0 |
| Studio typecheck | `cd apps/studio && pnpm.cmd check` | exit 0 (only needed if you touch studio callers per 9c STOP check) |

## Scope

**In scope**:
- `server/src/geofront_api/routers/ingest.py`
- `server/src/geofront_api/routers/agent/playbooks.py`
- `server/src/geofront_api/routers/feedback.py`
- `server/src/geofront_api/routers/workspace.py` (create route only)
- `server/src/geofront_api/schemas.py` (field validators)
- `server/tests/test_input_validation.py` (create)

**Out of scope**:
- `libs/geoagent/src/geoagent/playbooks.py` — the lib-level
  `save_playbook` keeps its permissive behavior for CLI use; the gateway
  validates before calling. (A lib-side hardening is a separate change.)
- Studio/web callers beyond reading them for the 9c STOP check.
- Auth/deployment posture (plan 011 / separate decision).
- Any route not listed above.

## Git workflow

- Branch: `advisor/009-input-validation-sweep`
- Commits (one per sub-fix, reviewable):
  `fix(server): reject path-bearing upload filenames`,
  `fix(server): validate playbook names before filesystem use`,
  `fix(server): confine feedback export to a server-managed directory`,
  `fix(server): enforce the documented workspace-name charset`,
  `fix(server): map /asset malformed input to 422`

## Steps

### Step 1 (9a): sanitize upload filenames

Add to `ingest.py`:

```python
def _safe_upload_name(filename: str) -> str:
    """Reject path-bearing upload names before they reach the filesystem."""
    name = (filename or "").strip()
    if not name:
        raise GeoFrontError(code="invalid_filename", message="Filename is required.", status_code=422)
    if Path(name).name != name or "/" in name or "\\" in name or ":" in name or name.startswith("."):
        raise GeoFrontError(
            code="invalid_filename",
            message="Filename must be a bare file name (no path separators).",
            status_code=422,
        )
    return name
```

Apply it at the top of `ingest_file` (`ingest.py:126-130`, before
`_check_extension`), in `ingest_bytes` (after `_check_extension`), and in
`create_asset`'s multipart and JSON branches. `Path(name).name != name`
catches `..`-components and nested paths; the explicit checks catch Windows
separators/drive letters and dotfiles.

**Verify**: `conda run -n geo pytest server/tests/test_ingest_validation.py -q` after Step 5 (write tests first if you prefer TDD; both orders acceptable).

### Step 2 (9b): validate playbook names

In `routers/agent/playbooks.py`, add and apply:

```python
import re
_PLAYBOOK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

def _validate_playbook_name(name: str) -> None:
    if not _PLAYBOOK_NAME_RE.match(name):
        raise GeoFrontError(code="invalid_playbook_name", message=f"Invalid playbook name: {name!r}", status_code=422)
```

Call it at the start of `get_playbook` and in the save route before
`save_playbook`. As defense-in-depth, after building `target` in
`get_playbook` assert containment:

```python
resolved = target.resolve()
if not resolved.is_relative_to((service.settings.workspace / "playbooks").resolve()):
    raise GeoFrontError(code="path_outside_sandbox", message="Playbook path escapes the playbooks directory", status_code=403)
```

**Verify**: `conda run -n geo pytest server/tests -q` → existing agent tests pass.

### Step 3 (9c): confine feedback export

Grep first: `grep -rn "feedback/export" apps/` — if any frontend passes
`output_dir`, STOP and report (the owner must decide whether to keep the
parameter, e.g. confined to the workspace dir). If nothing passes it:

- Change the handler to ignore the query parameter entirely (remove it from
  the signature — FastAPI drops it from OpenAPI) and always export to
  `Path(tempfile.mkdtemp())`. Keep the FileResponse behavior unchanged.

**Verify**: `conda run -n geo pytest server/tests -q` → feedback tests pass (if the route has tests; if none, note that).

### Step 4 (9d): enforce the workspace-name charset

In `routers/workspace.py` create route, replace the strip-only line:

```python
import re
_WS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,80}$")
name = req.name.strip()
if not name or not _WS_NAME_RE.match(name) or ".." in name:
    raise GeoFrontError(
        code="invalid_workspace_name",
        message="Workspace name may contain letters, digits, spaces, '.', '-', '_' and must not start with a dot.",
        status_code=422,
    )
safe_name = name
```

(Alternative placement: a Pydantic `field_validator` on
`CreateWorkspaceRequest.name` in `schemas.py` returning 422 automatically —
prefer that if it matches how other request models validate; check
`schemas.py` for existing validators first and follow them. Either is
acceptable; pick one and delete the other.)

**Verify**: existing workspace tests pass.

### Step 5 (9e): map `/asset` malformed input to 422

In `routers/ingest.py` `create_asset`:

- Wrap `body = await request.json()` in try/except → 422
  `invalid_json` (mirror the `GeoFrontError` style of `ingest.py:139-142`).
- Wrap `base64.b64decode(body["data_base64"])` in try/except
  `(binascii.Error, ValueError)` → 422 `invalid_base64`, exactly like the
  sibling route.

### Step 6: Tests

Create `server/tests/test_input_validation.py` (follow the client/fixture
style of `server/tests/test_ingest_validation`-adjacent tests — check
`server/tests/conftest.py` for the app client fixture):

1. `/ingest` multipart with filename `../evil.txt` → 422 `invalid_filename`;
   `C:\evil.txt` → 422.
2. `/ingest/bytes` with `filename: "../evil.txt"` → 422.
3. `GET /agent/playbooks/..%2F..%2Fsettings` → 422 `invalid_playbook_name`;
   `POST /agent/playbooks/save` with `name: "../x"` → 422.
4. `GET /api/v1/feedback/export?task_type=...&output_dir=C:/Windows/Temp` →
   succeeds but the returned file lives in a temp dir, NOT the requested
   one (assert via the response `Content-Disposition` path or that the
   requested dir was never created — pick the assertable form).
5. `POST /api/v1/workspace/create` with `name: "../../foo"` → 422
   `invalid_workspace_name`.
6. `POST /api/v1/asset` (JSON branch) with invalid JSON body → 422 (not
   500); with `"data_base64": "not-base64!!"` → 422 `invalid_base64`.

**Verify**: `conda run -n geo pytest server/tests/test_input_validation.py -q` → all pass; full suite 156+ passed.

## Test plan

- New `server/tests/test_input_validation.py` covering 9a-9e.
- All existing server tests unchanged and green.
- Verification: full suite + lint + mypy green.

## Done criteria

- [ ] `grep -n "_safe_upload_name" server/src/geofront_api/routers/ingest.py` → applied at 3 call sites
- [ ] New validation tests all pass; full server suite green
- [ ] `conda run -n geo ruff check server` → exit 0
- [ ] `cd server && conda run -n geo mypy --strict src/` → exit 0
- [ ] No changes outside scope (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any frontend actually passes `output_dir` to `/feedback/export` (check
  `apps/web` and `apps/studio`) — report; removing the param would break a
  real flow.
- The save-playbook route's request model or the geoagent `save_playbook`
  signature differs from the excerpts — report.
- Existing tests intentionally exercise traversal names as valid inputs —
  report (they'd need owner sign-off to invert).

## Maintenance notes

- This plan closes the input-side holes only; exposure still depends on
  the deployment bind posture (see plan 011 and the audit's SECURITY-01).
- When a shared path-validation helper lands (the audit's DEBT-04), these
  route-local checks can delegate to it — keep the error codes stable.
- Reviewer should scrutinize: error codes match the repo envelope style;
  no legit filename that the studio/web apps already send gets rejected
  (grep the frontends for upload calls to double-check typical names).
