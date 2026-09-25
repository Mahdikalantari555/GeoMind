# AGENTS.md — GeoFoundation

> Guidance for AI coding agents working in this repository. Authoritative
> specs: `docs/` (CHARTER, ARCHITECTURE, STRUCTURE, SPEC_SERVER, SPEC_WEB)
> and `openspec/`. Feature work goes through openspec changes.

## What this is

GeoFoundation is a **data-sovereign AI platform for remote sensing research**.
Knowledge (workspaces, documents, rasters, feedback) stays local; LLM compute
is hybrid — remote OpenAI-compatible API **by default**, local GGUF fallback.

Monorepo assembling:

| Path | Role |
|---|---|
| `libs/geomemory/` | memory engine (hybrid search, citations, feedback) — has its own AGENTS.md, follow it when working inside |
| `libs/geoagent/` | agent SDK (tool registry, playbooks, LLM loop) |
| `libs/data_engine/` | Landsat/Sentinel-2 processing (METRIC ETa, NDVI pipelines) |
| `libs/geolearn/` | online/frozen-adaptation ML layer |
| `server/` | FastAPI gateway `geofront_api` — `/api/v1`, the ONLY surface apps consume |
| `apps/web/` | React Vite SPA (en/fa RTL), generated API client |
| `docs/`, `openspec/` | root-level specs and cross-lib change proposals |

## Environment & commands

All Python runs in the **`geospatial` conda env** (only env with the libs
installed — `conda env list` confirms it; the `ai` env referenced in
`libs/geomemory/AGENTS.md` does not exist, ignore it).

```bash
# install (editable) python libs
conda run -n geospatial pip install -e libs/geomemory -e libs/geoagent -e server

# server tests
conda run -n geospatial pytest server/tests -q
conda run -n geospatial ruff check server
conda run -n geospatial mypy --strict server/src

# web — pnpm (no lockfile present, so `pnpm install` regenerates one)
cd apps/web && pnpm install
pnpm lint && pnpm build && pnpm test        # vitest + jsdom
pnpm gen:api                               # regenerate client from running gateway

# run dev stack
conda run -n geospatial uvicorn geofront_api.main:app --port 8000
cd apps/web && pnpm dev                    # :5173 proxies /api → :8000
```

Mypy runs per-project from each project's directory (each has its own
`pyproject.toml` with `strict=true` and `disable_error_code=["import-untyped"]`):
```bash
cd libs/geomemory && conda run -n geospatial mypy --strict src/
cd libs/geoagent   && conda run -n geospatial mypy --strict src/
cd server          && conda run -n geospatial mypy --strict src/
```
Ruff across all projects from root:
`conda run -n geospatial ruff check libs/data_engine/src libs/geoagent/src libs/geomemory/src server/src`.

Known pre-existing failure (in libs/geomemory, not ours to fix here):
`geomemorytest/test_workspace_lifecycle.py::TestAskAbstention::test_ask_no_model_abstains_when_context_exists`.

## Invariants (do not break)

1. **Apps consume only the gateway HTTP API.** `apps/web` never imports
   `geomemory`/`geoagent`; the gateway never imports library internals —
   public facades only (`geomemory`, `geoagent` top-level APIs).
2. **SQLite single writer**: server runs one uvicorn worker, holds one
   active workspace, serializes writes behind the asyncio lock in
   `server/src/geofront_api/state.py`.
3. **Secrets handling.** LLM API keys are read from the env var named by
   `llm_api_key_env` (default `GEOMEMORY_LLM_API_KEY`). Keys **MAY** be set
   at runtime via `PUT /api/v1/workspace/settings` field `llm_api_key` → the
   gateway sets `os.environ[effective_key_env]` in-process (never persisted to
   workspace DB, never returned); `llm_api_key_env` itself may be updated.
   Keys are read from env at call time; never persisted, never returned.
4. **Blocking facade calls run in a threadpool** (`anyio.to_thread`) —
   never call the sync libs directly on the event loop.
5. **Content identity = SHA-256; provenance chain stays traceable**:
   answer → citation → segment → asset_revision → objects/<sha256>.
6. **Embedding spaces are isolated per modality** (text.* vs vision ids).
7. `workspace/`, `.env`, models, `node_modules/`, venvs are **never
   committed** (root .gitignore enforces).

## Conventions

- Python: ≥3.10, strict typing, Pydantic v2, ruff line-length 100, mypy
  strict. Error responses use the envelope `{error: {code, message, detail?}}`.
- Long operations are background jobs: `202 {job_id}` → `GET /api/v1/jobs/{id}`.
- Realtime: SSE at `GET /api/v1/events`; web invalidates TanStack Query
  caches from events, no polling staleness.
- Web: TS strict, ESLint + Prettier, shadcn/ui + Tailwind **logical
  properties** (`ps/pe/ms/me` — never `pl/pr`) for RTL safety; all user
  strings via i18next (`en`/`fa`). LLM-unavailable = abstention UI state,
  never a crash.
- Commits: one concern per commit; `libs/` changes never mixed with
  server/app changes. Per-lib tags: `libs/<name>/vX.Y.Z`.
- New features: `openspec change` proposal first, implement against
  `tasks/todo.md`, archive when done.

## Where things live

- Server routers: `server/src/geofront_api/routers/` (one file per domain;
  agent subpackage under `routers/agent/`).
- Web features: `apps/web/src/features/<domain>/` — page, components, hooks
  together; shared widgets in `src/components/`.
- Gateway contract: OpenAPI schema is source of truth; regenerate the web
  client after any route change (`pnpm gen:api`) and fix type errors before
  merging.
- **OpenSpec changes**: each lib owns its own `openspec/changes/` directory at
  its root (`libs/geomemory/openspec/changes/`, `libs/geolearn/openspec/changes/`,
  `libs/data_engine/openspec/changes/`). Only cross-lib or server/web-only
  changes live under `openspec/changes/` at the repo root. Archived changes
  stay alongside their originating directory — do not leave archive copies in
  both places.

## Working rules

- Don't edit `libs/*` unless the task explicitly says so — libs have their
  own specs, tests, and release discipline. Missing capability in a lib =
  separate change proposal in that lib.
- Don't invent requirements beyond `docs/` + `openspec/` + user instruction.
- Run lint + tests before committing (Python and/or web depending on what
  changed).
- Update `tasks/todo.md` checkboxes as tasks complete.
## Codebase Search & Discovery Rule (MANDATORY)

**ALWAYS use `zg` (`zvec-grep_zvec_grep_search`) and `codebase-memory` (`search_graph`, `trace_path`, `get_code_snippet`, etc.) for searching and exploring the codebase.**
Do NOT use ripgrep, grep, or file globbing for semantic or structural codebase discovery unless falling back for exact string literals, error messages, or unindexed files.

## Codebase Memory — structural graph

This repo is also indexed in the **codebase-memory** knowledge graph
(`home-asus-Projects-GeoFoundation`, 12,283 nodes / 41,051 edges). Use these MCP
tools for structural queries that grep can't answer:

| Tool | Use for |
|---|---|
| `search_graph` | Find functions/classes by name or natural language (BM25 + camelCase splitting). Returns file:line + rank. |
| `trace_path` | Who calls X? What does X call? Transitive callers/callees with cursor pagination. |
| `get_code_snippet` | Full source of a function/class by qualified_name. |
| `query_graph` | Cypher queries — complexity, loop depth, hot spots, cross-layer edges. |
| `get_architecture` | Overview, routes, clusters, layers, boundaries, entry points. |
| `detect_changes` | Blast radius of uncommitted or recent changes. |

Prefer these over grep for structural discovery. Fall back to grep for string
literals, error messages, or files flagged `parse_partial` in `index_status`.

### Re-indexing

The index is built from source; re-run after significant changes:
```bash
codebase-memory_index_repository --repo /home/asus/Projects/GeoFoundation --mode full
```

## zvec-grep (zg) — semantic/hybrid search

This repo is also indexed in **zvec-grep** (CLI: `zg`, MCP:
`zvec-grep_zvec_grep_search`). Use it for semantic, relational, cross-file, or
multi-hop evidence such as architecture, call chains, dependencies, lifecycle,
data or control flow, and design rationale — when exact symbol lookup alone
can't answer the question.

| Tool | Use for |
|---|---|
| `zvec-grep_zvec_grep_search` | Natural-language hybrid search (FTS + vector). Returns file:line, outline, and source snippets. Scope with `globs` (e.g. `server/**/*.py`). |

Results include bounded source snippets and query-group metadata; treat
sufficient snippets as already-read evidence. Read freshness and
`background_refresh` from the response without a status preflight; when results
are served from a current index, use them if sufficient.

**Complements, doesn't replace, codebase-memory-mcp.** Use zg for semantic /
cross-file / multi-hop questions and codebase-memory-mcp for structural graph
queries (callers, callees, blast radius, complexity). Fall back to native Grep
for exact string literals, error messages, or files flagged `parse_partial`.

### Index management

The index lives under `<root>/.zvec-grep/` and is built from source with a
local embedding model (`potion-code-16m-v2`). Rebuild after significant changes:

```bash
zg index /home/asus/Projects/GeoFoundation            # build
zg index /home/asus/Projects/GeoFoundation --rebuild   # rebuild
zg status                                              # coverage + freshness
```

The MCP server refuses to search without a built index and will not auto-create
one without explicit authorization — build it once before relying on it.
