# Proposal: product-hardening-and-trust

> Large cross-cutting change. Root `openspec/changes/` per AGENTS.md (server,
> multi-lib and CI/docs work belongs here). It merges the audit's security,
> integrity, verification and DX findings into one executable tranche.

## Why

The 2026-11-22 audit at commit `673908a` (`plans/AUDIT-2026-11-22.md`) found
100 product-readiness issues. Roughly half are not feature gaps but **trust
defects**: the gateway has no authentication while publishing `0.0.0.0:8000`,
a vector-DB credential is echoed and written cleartext, SSE broadcasts other
clients' job results, the agent tool sandbox misses write paths and CLI args,
SQLite migrations are not atomic, soft-deleted documents stay searchable, two
entropy formulas disagree on abstention, and the "strict typing" CI gate only
checks changed files while ~46 pre-existing errors are exempt.

These defects compound: a prompt-injected tool call can write an arbitrary
file that a workspace plugin then executes on next startup; a bad migration
leaves DDL applied with no version row. Fixing them as one tranche is faster
than sixlib-by-lib changes because they share verification infrastructure and
a common security model. This change is the prerequisite for presenting the
product beyond a trusted loopback demo.

## What Changes

**Gateway (S-006…S-015, G-024…G-033):**
- Add a gateway-wide bearer-token auth dependency (`GEOMIND_API_TOKEN`) with a
  local-dev opt-out and an admin scope for settings/providers/environment/model
  routes; bind `127.0.0.1` by default (`GEOMIND_BIND=0.0.0.0` to opt out) and
  make CORS origins env-driven.
- Route `qdrant_api_key`/`cloudflare_api_token` through the never-persisted env
  path used by `llm_api_key`; mark the lib fields `exclude=True`; return only
  configured flags. Rotate any key ever written to a workspace.
- Strip `input`/`ctx` from 422 error details; publish only job id/status/
  progress in SSE (no `result`); replace raw `str(exc)` with stable codes +
  correlation ids; strip workspace/key fields from `/health`.
- Typed Pydantic bodies for feedback routes and typed GeoJSON `roi`; normalize
  paths in `agent/files.py`; reconcile `farms.py` roots with `maps.py`.
- Wrap `AgentService.init()` in `run_in_threadpool`; make job progress
  loop-safe; bound the job registry by total count; add cooperative shutdown
  cancellation; report partial downloads explicitly; cache rendered tiles.

**Agent / learning / domain (S-018…S-023, L-060…L-069, P-070):**
- Reject absolute paths for all write args (`output_*`/`out_*`), validate CLI
  path params, intersect `context_scope` collections with the allowlist, pin
  plugin hashes before `exec_module`, wrap untrusted tool text in explicit
  "never follow instructions" blocks, validate classifier key components.
- Give nested tool calls a shared budget counter/deadline; pass a real
  `meteo_data` dict instead of `cast(dict, [])`.
- Skip malformed training candidates; standardise on one normalized entropy
  function and threshold scale; make edge probabilities match the trained
  classifier; stop mutating the caller's `ConfidenceModel`.
- Make `polygonize_array` CRS-aware; delegate `geo_reclassify` to the core
  validation; unify the stress-class taxonomy under geodomain's versioned
  definition; remove the duplicate `StreamingWindow`; make version paths
  explicit; use `timezone.utc` for the declared 3.10 floor; wire or delete
  `auto_train_on_feedback` and reset drift after adaptation.

**Geomemory (M-050…M-059, P-071…P-075, S-007 lib side):**
- Make migrations atomic (no `executescript` implicit commit); exclude
  soft-deleted assets from FTS/dense/image search; rollback before retrying a
  locked write; honour configured `objects_dir`; give image/candidate
  citations a traceable target type; isolate event subscribers; parse
  timestamps before temporal filters; check space/model compatibility; remove
  the invalid `turn_id` persistence branch; make `min_score` a normalized
  relevance threshold.
- Cache the embedder and n-gram backend with invalidation; batch image/relation
  N+1 lookups; replace the candidate `LIKE` scan with FTS; bound the
  `retrieval_run` log. Coordinate with the already-open
  `harden-sqlite-write-contention` change (do not duplicate it).

**Verification, DX and docs (T-081…T-083, X-084…X-092, CI/deps):**
- Run the `geomemorytest/` suite in CI with the known failure marked
  `xfail(strict=True)`; replace changed-files-only lint/mypy with a
  characterisation baseline that fails only on new violations; add
  `pip-audit`/`pnpm audit` reporting; share one conda env across CI jobs.
- Remove the duplicate `httpx2` line; decide and enforce one Python floor
  across `requires-python`, ruff/mypy targets, `environment.yml` and Docker;
  add license metadata to the three libs missing it.
- Pick one conda env name (`geo` vs `geospatial`) and align docs/launchers;
  fix the README `cd` sequence; document all env vars in `.env.example`;
  pin pnpm via `packageManager`; replace `wait -n` for macOS bash 3.2.
- Correct `SPEC_WEB.md` (SvelteKit → React, stack list), the sample-pipeline
  spec paths, the privacy/auth claims and the `GEOFONT_STATE_PATH` typo.

## Capabilities

### Modified Capabilities
- `gateway-server` — auth, secrets, errors, events, input contracts, jobs, tiles.
- `error-observability` — correlation ids instead of raw exception text.
- `agent-runtime` — sandbox containment, shared budgets, trusted tool output.
- `geolearn-adaptation-reliability` — one entropy scale, clean training data,
  working feedback toggle.
- `retrieval-parity` — soft-delete visibility, relevance thresholds, provenance.
- `ci-ready-output` — whole-tree verification baseline and dependency audits.

## Impact

- Nearly every directory is touched, but the edits are mostly local and
  additive. Highest blast radius: gateway auth (must roll out with Studio token
  transport), geomemory search filters (change what is retrievable), and the
  taxonomy unification (changes report labels).
- **Security:** any key ever echoed or written to a workspace must be rotated;
  the report references locations and credential types only.

## Dependencies

- Land this before `studio-product-completion` (Studio must send the token and
  read configured flags) and `ship-and-measure-agent`.
- Coordinate with the open `harden-sqlite-write-contention` geomemory change
  and `publish-agent-baseline` (benchmark regression hook).
- No lib source edits happen outside the per-lib changes; where a root-cause
  fix sits in a lib, that lib's tests must be updated in this same change.

## Out of Scope

- Per-user credential isolation / multi-user authz (documented future phase).
- The Studio UI work, scene previews/bands and Sentinel-1 (other changes).
- Full OS keyring / encrypted secret storage; keep mode 0600 + documented
  `persist_secrets` tradeoff.
- Replacing the agent thread pool with process isolation (documented limit).

## Findings covered

S-006…S-023, G-024…G-033, M-050…M-059, P-070…P-075, L-060…L-069,
T-081, T-082, T-083, X-084…X-093, CI-01…03, DEP-01…03, DOC-01…05,
F-099 (auto-train/drift), plus the lower-priority security/test items listed
in the audit's "additional vetted findings" appendix.
