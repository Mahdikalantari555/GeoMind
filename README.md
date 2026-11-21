# GeoMind

**The data-sovereign remote-sensing agent.** Draw a box on
the map, download the satellite data behind it, ask questions over your own
knowledge, and watch a small model learn from every answer you correct — all
on your machine. Every answer cites its sources or abstains; nothing is
fabricated.

Your data never leaves your machine. Compute is pluggable: a remote
OpenAI-compatible LLM API by default, a local GGUF model for full offline.

## The 60-second demo

1. **Draw → Download.** Select any ROI, search Landsat/Sentinel-2 scenes,
   download with live progress over SSE.
2. **Ask → Cite.** Grounded QA over your documents and rasters — every claim
   links back to the exact segment (`answer → citation → segment → asset`).
3. **Correct → Learn.** Accept feedback, hit *Train now*, and watch the
   online classifier update on CPU in seconds.

## Layout

```
libs/
  geomemory/        memory engine (SQLite+FTS5+RTree, hybrid search, citations, feedback)
  geoagent/         agent SDK (tool registry, playbooks, LLM loop)
  geolearn/         online learning layer (partial_fit, calibration, versioning)
  data_engine/      Landsat/Sentinel-2 pipelines (METRIC ETa) + scene fetcher
  geospatial_core/  raster/vector primitives (indices, zonal stats)
  geodomain/        pure domain contracts
server/            FastAPI gateway — /api/v1, the only surface apps consume
apps/
  studio/           GeoMind Studio — map-first product front (React 19 + MapLibre)
  web/              admin/ops console (React Vite SPA, en/fa RTL)
docs/              CHARTER · ARCHITECTURE · STRUCTURE · SPEC_SERVER · SPEC_WEB
```

**One rule:** dependencies point strictly downward
(`apps → gateway → libs → storage`). Apps never import libs directly — the
gateway's OpenAPI contract is the only interface.

## Quickstart (dev)

Python runs in the **`geo` conda env** (Windows/Linux; see AGENTS.md):

```bash
# python libs (conda env `geo`)
conda run -n geo pip install -e libs/geodomain -e libs/geospatial_core -e libs/data_engine -e libs/geolearn -e libs/geomemory -e libs/geoagent -e server

# gateway
conda run -n geo uvicorn geofront_api.main:app --port 8000

# studio (map-first product front)
cd apps/studio && pnpm install && pnpm dev    # :5174, proxies /api → :8000

# admin console
cd apps/web && pnpm install && pnpm dev       # :5173, proxies /api → :8000
```

Or one command: `./run-studio.sh` (gateway + studio).

## Docker (single-box demo)

```bash
# gateway (8000) + web (5173 → nginx proxy to gateway)
# workspace is a named volume; mount a host dir with -v /host/ws:/workspace if needed
GEOMEMORY_LLM_API_KEY=sk-... docker compose up --build -d
curl http://localhost:8000/health
open http://localhost:5173

# logs
docker compose logs -f gateway web

# stop
docker compose down
```

The web image is a multi-stage Vite → nginx build; the gateway is
`python:3.12-slim` with a single uvicorn worker (SQLite single-writer
invariant, AGENTS.md § Invariants).

## Design values

1. **Citations or abstention** — no silent hallucination, ever.
2. **Map is home** — geospatial is the identity, not a feature.
3. **Progress is a right** — long ops stream over SSE (`job.progress`).
4. **Agent parity** — agent tools and UI pages share one API.
5. **Local-first, hybrid compute** — remote LLM by default, GGUF offline.
6. **Frugal ML** — training on CPU in seconds, visible in the UI.

## Docs

Start with `docs/CHARTER.md` (vision + roadmap), then
`docs/ARCHITECTURE.md`, `docs/STRUCTURE.md`, and the specs
(`SPEC_SERVER.md`, `SPEC_WEB.md`). Product vision:
`research/startup-vision/VISION.md`.

## License

MIT — see [LICENSE](LICENSE).
