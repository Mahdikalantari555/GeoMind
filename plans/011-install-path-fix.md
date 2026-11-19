# Plan 011: Repair the advertised install paths (Docker image + README quickstart)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on.
> If a STOP condition triggers, stop and report — do not improvise. When
> done, update the status row for this plan in `plans/README.md` — unless a
> reviewer dispatched you and maintains the index.
>
> **Drift check (run first)**: `git diff --stat 2b85a31..HEAD -- server/Dockerfile README.md`
> Compare the "Current state" excerpts against live code; on mismatch, STOP.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: deps / dx
- **Planned at**: commit `2b85a31`, 2026-11-14

## Why this matters

Both advertised install paths are broken:

1. **`docker compose up --build` fails at the pip layer.** `libs/geomemory`
   declares `geodomain` and `geospatial_core` as hard dependencies, but they
   are not published to PyPI (per `environment.yml:69-71` comments) — a
   bare `pip install -e libs/geomemory` cannot resolve them. The Dockerfile
   also never copies or installs `data_engine`, `geolearn`, `geodomain`, or
   `geospatial_core`, so even a repaired dependency resolution would leave
   the gateway's `/api/v1/data/*` routes (which import
   `data_engine.fetch`) failing at runtime with ImportError.
2. **The README quickstart install line is wrong** — it omits
   `libs/geodomain` and `libs/geospatial_core`, so a fresh `pip install -e
   libs/geomemory ...` per README:48 fails to resolve, exactly like the
   image build.

These are the first two commands a new user (or investor demo) touches.

## Current state

- `server/Dockerfile:15-30`:
  ```dockerfile
  # Copy dependency manifests first for layer caching
  COPY libs/geomemory/pyproject.toml libs/geomemory/README.md* libs/geomemory/
  COPY libs/geoagent/pyproject.toml libs/geoagent/README.md* libs/geoagent/
  COPY server/pyproject.toml server/README.md* server/

  # Copy sources (install needs package data)
  COPY libs/geomemory/src libs/geomemory/src
  COPY libs/geomemory/geomemorytest libs/geomemory/geomemorytest
  COPY libs/geoagent/src libs/geoagent/src
  COPY libs/geoagent/tests libs/geoagent/tests
  COPY server/src server/src

  RUN pip install --upgrade pip \
   && pip install -e libs/geomemory \
   && pip install -e libs/geoagent \
   && pip install -e server
  ```
- `README.md:42-58` (quickstart):
  ```markdown
  ## Quickstart (dev)

  Python runs in the **`geo` conda env** (Windows/Linux; see AGENTS.md):

  ```bash
  # python libs (conda env `geo`)
  conda run -n geo pip install -e libs/geomemory -e libs/geoagent -e libs/geolearn -e libs/data_engine -e server
  ```
- **The correct install order** (dependency order, from
  `.github/workflows/ci.yml:32-41`):
  ```yaml
  pip install \
    -e libs/geodomain \
    -e libs/geospatial_core \
    -e libs/data_engine \
    -e libs/geolearn \
    -e libs/geomemory \
    -e libs/geoagent
  ```
  (and the server job appends `-e 'server[dev]'`).
- `libs/geomemory/pyproject.toml` declares `geodomain>=0.1.0` and
  `geospatial_core>=0.1.0` as hard deps; `environment.yml:69-71` documents
  that they are not on PyPI.
- The gateway imports data_engine at module level:
  `server/src/geofront_api/routers/data.py:18` → `from data_engine.fetch import ...`
  (and `geolearn` is imported lazily inside the training route, so it must
  be installed too but failure mode differs).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Docker build | `docker build -f server/Dockerfile .` | exit 0 (if docker is available) |
| Import smoke check inside image | `docker run --rm <image> python -c "import geofront_api.main"` | exit 0 |
| README line check | `grep -n "pip install -e" README.md AGENTS.md` | both include all libs |
| Server tests (unchanged) | `conda run -n geo pytest server/tests -q` | 156 passed |

If `docker` is not available in the executor environment, verification of
Step 1 is a careful re-read of the final Dockerfile plus a local
simulation (Step 1b below); say so in the report.

## Scope

**In scope**:
- `server/Dockerfile`
- `README.md` (quickstart install line only)
- `AGENTS.md` install line (only if it omits the same libs — check; it
  currently includes them, in which case no edit)

**Out of scope**:
- `server/Dockerfile:22` copying `libs/geomemory/geomemorytest` (legacy test
  suite shipped in the image) — tracked as separate debt; leave as-is.
- CI image-build job (a follow-up worth adding, noted in Maintenance).
- `docker-compose.yml`, root `requirements.txt`, `environment.yml` (separate
  dependency-sprawl debt).
- Any lib's `pyproject.toml`.

## Git workflow

- Branch: `advisor/011-install-path-fix`
- Commits: `fix(docker): install all six libs in the gateway image`, `docs(readme): correct the quickstart install line`

## Steps

### Step 1: Add the four missing libs to the Dockerfile

Extend the COPY and install blocks (order = dependency order, mirroring CI):

```dockerfile
# Copy dependency manifests first for layer caching
COPY libs/geodomain/pyproject.toml libs/geodomain/README.md* libs/geodomain/
COPY libs/geospatial_core/pyproject.toml libs/geospatial_core/README.md* libs/geospatial_core/
COPY libs/data_engine/pyproject.toml libs/data_engine/README.md* libs/data_engine/
COPY libs/geolearn/pyproject.toml libs/geolearn/README.md* libs/geolearn/
COPY libs/geomemory/pyproject.toml libs/geomemory/README.md* libs/geomemory/
COPY libs/geoagent/pyproject.toml libs/geoagent/README.md* libs/geoagent/
COPY server/pyproject.toml server/README.md* server/

# Copy sources (install needs package data)
COPY libs/geodomain/src libs/geodomain/src
COPY libs/geospatial_core/src libs/geospatial_core/src
COPY libs/data_engine/src libs/data_engine/src
COPY libs/geolearn/src libs/geolearn/src
COPY libs/geomemory/src libs/geomemory/src
COPY libs/geomemory/geomemorytest libs/geomemory/geomemorytest
COPY libs/geoagent/src libs/geoagent/src
COPY libs/geoagent/tests libs/geoagent/tests
COPY server/src server/src

RUN pip install --upgrade pip \
 && pip install -e libs/geodomain \
 && pip install -e libs/geospatial_core \
 && pip install -e libs/data_engine \
 && pip install -e libs/geolearn \
 && pip install -e libs/geomemory \
 && pip install -e libs/geoagent \
 && pip install -e server
```

Check each lib for extra data files its pyproject includes (e.g.
`libs/geomemory` ships `schema.sql` inside `src/` — covered). If a lib has
no `README.md`, the `README.md*` glob covers absence — but verify the COPY
source path exists for every line you add (`ls libs/<name>/`).

**Verify (docker available)**: `docker build -f server/Dockerfile -t geomind-gateway-check .` → exit 0; then
`docker run --rm geomind-gateway-check python -c "import geofront_api.main; import data_engine.fetch; import geolearn; import geospatial_core; import geodomain; print('ok')"` → prints `ok`.

**Verify (no docker — Step 1b simulation)**: in the conda env, confirm each
lib installs standalone in dependency order without network resolution of
the local libs:
`conda run -n geo pip install -e libs/geodomain -e libs/geospatial_core -e libs/data_engine -e libs/geolearn` → exit 0 (they are likely already installed; use `--no-deps --force-reinstall` only if needed to simulate a fresh install, and restore afterwards). Report which simulation you ran.

### Step 2: Fix the README quickstart

`README.md:48` becomes (matching AGENTS.md and CI):

```bash
conda run -n geo pip install -e libs/geodomain -e libs/geospatial_core -e libs/data_engine -e libs/geolearn -e libs/geomemory -e libs/geoagent -e server
```

Check `AGENTS.md:39` — it already lists the full editable set including
geodomain/geospatial_core; if so, no AGENTS.md edit.

**Verify**: `grep -n "pip install -e" README.md` shows all seven `-e` entries.

### Step 3: Sanity check the gateway still passes its suite

The Dockerfile change cannot affect the local env, but run the suite to
certify no accidental edits crept in.

**Verify**: `conda run -n geo pytest server/tests -q` → 156 passed.

## Test plan

- Docker build + import smoke check (Step 1 verify), or the 1b simulation
  with an explicit report of what was and wasn't verified.
- No new unit tests — this is config/docs; the existing suites are the
  regression net.

## Done criteria

- [ ] `server/Dockerfile` COPYs and installs all six libs + server
- [ ] `grep -c "pip install -e" server/Dockerfile` → 7 (six libs + server)
- [ ] README quickstart line matches CI order and includes geodomain +
      geospatial_core
- [ ] Docker build + import smoke check exit 0 (or 1b simulation documented)
- [ ] `conda run -n geo pytest server/tests -q` → 156 passed
- [ ] No other files modified
- [ ] `plans/README.md` status row updated

## STOP conditions

- Any lib's `pyproject.toml` declares a dependency that cannot be satisfied
  inside the slim python:3.12 image (heavy system deps like GDAL system
  libraries) and the build fails on it after one honest attempt — report
  the failing dependency; the image may need an apt package decision by the
  owner.
- A lib has no `src/` layout (flat layout) making the COPY lines wrong —
  report the actual layout.
- `docker` unavailable AND the 1b simulation cannot run — report; do not
  claim the image builds.

## Maintenance notes

- Follow-up (not this plan): add a CI job that builds
  `server/Dockerfile` on every push so this cannot regress silently.
- The image still ships `libs/geomemory/geomemorytest` (legacy suite) —
  tracked separately; removing it touches this same COPY block, so revisit
  when that debt lands.
- Reviewer should scrutinize: install order matches CI exactly; no lib
  data files (schema.sql etc.) missed by the COPY lines.
