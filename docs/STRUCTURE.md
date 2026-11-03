# GeoMind — Structure & Conventions

## Artifact taxonomy

| Library | Examples | Travels as |
|---|---|---|
| Library | geomemory, geoagent, geolearn, data_engine | pip package (git tag / path dep) |
| Gateway | server/ | container / uvicorn |
| App | apps/web, CLI, (future) MCP | static bundle / binary / protocol server |
| Workspace | SQLite + objects/ + runs/ | filesystem dir, zip archive — **never pip, never git** |
| Model weights | GGUF, .pth | model cache dir — **never git** |
| Case study | experiment code + configs + evals | own folder/repo with pinned deps + lockfile |

## Conda env

All Python work runs in the `geospatial` conda env (the only env with the libs
installed — the `ai` env referenced in geomemory CLAUDE.md does not exist):

```bash
conda run -n geospatial pip install -e libs/geomemory -e libs/geoagent \
  -e libs/geolearn -e libs/data_engine -e server
conda run -n geospatial pytest server/tests -q
conda run -n geospatial ruff check server
conda run -n geospatial mypy --strict server/src
```

Known pre-existing failure (in libs/geomemory, not ours to fix here):
`geomemorytest/test_workspace_lifecycle.py::TestAskAbstention::test_ask_no_model_abstains_when_context_exists`.

## Adding a library

1. Folder lands in `libs/<name>/` with src-layout + pyproject + tests.
2. `pip install -e libs/<name>` into `geospatial`.
3. Import name = folder name (naming symmetry, zero surprises).
4. Tag before anything pins it: `git tag libs/<name>/v0.1.0`.
5. For libraries with their own history (e.g. `data_engine`), copy via subtree
   import or plain copy, then `git add libs/<name>`, editable install.

## Subtree note (history preservation)

`libs/geomemory` was imported with full history:

```bash
git subtree add --prefix=geomemory ../GeoMemory main
git mv geomemory libs/geomemory
```

`libs/data_engine` was integrated from the legacy METRIC repository as
`libs/metric_et`, then renamed to `libs/data_engine`. If the source repository
is ever made a git repo, the same subtree pattern can be used to preserve
history.

Legacy siblings (`../GeoMemory`, `../GeoAgent`, `../geomemorytest`) are now
frozen copies — delete them only after confirming the monorepo works for a
few days. Do NOT edit them anymore.

## Case-study pattern (studies/, post-MSc or when first experiment starts)

```
studies/<name>/
├── pyproject.toml      # git-tag pinned deps + [tool.uv.sources] editable override
├── configs/            # yaml experiment configs
├── scripts/            # ingest.py · run.py · eval.py · report.py
├── evals/              # benchmark JSONLs (small, committed)
└── README.md           # workspace/model paths, how to reproduce
```

Dual-mode dependency trick (dev editable ↔ defense freeze):

```toml
[project]
dependencies = [
  "geomemory @ git+https://github.com/Mahdikalantari555/GeoMind.git@libs/geomemory/v0.1.0",
]

[tool.uv.sources]           # DEV ONLY — comment out + `uv lock` to freeze
geomemory = { path = "../../libs/geomemory", editable = true }
```

Rules:
- Studies touch only public facades (geomemory API, geoagent SDK). Needing
  an internal = feature request to the lib.
- Extract on second use: study-specific code graduates into `libs/` only
  when a second consumer appears (this is how GeoLearn will be born).
- Data/models/workspaces never committed; paths documented per-study.

## Versioning

- Monorepo trunk = `main`.
- Per-lib tags: `libs/<name>/vX.Y.Z` (subtree-friendly, unambiguous).
- Pre-1.0: exact pins everywhere (`==` / exact git tag).

## Git hygiene

- `workspace/`, `.env`, models, node_modules, venvs are gitignored globally.
- One concern per commit; `libs/` changes never mixed with app changes.
- Monorepo has no remote yet — add one before the next big milestone.
