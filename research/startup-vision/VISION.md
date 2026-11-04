# GeoMind Studio — Product Vision

> One app, one map, one loop. Svelte front end on the existing gateway.
> Status: vision draft, 2026-11-04. Companion to `research/startup-app-ux/REPORT.md`.

## The pitch

**A map-first studio where a researcher draws a box on a map, downloads the
satellite data behind it, asks questions over it, and watches a small model
learn from every answer they correct — all on their own machine.**

Three promises, all demo-able in under 5 minutes:

1. **Draw → Download.** Select any ROI, get Landsat/Sentinel data, see live
   progress. Fast, parallel, resumable.
2. **Ask → Cite.** Every answer cites segments or abstains. No hallucinated
   claims, ever.
3. **Correct → Learn.** Accepted feedback trains light models live, in the
   browser, on CPU.

## Why Svelte

- Small bundle; MapLibre interactions stay at 60fps on modest hardware.
- Stores map 1:1 onto SSE streams — job progress and agent tokens render
  declaratively.
- SvelteKit file-based routing fits the page layout below.
- Cost, stated honestly: `apps/web` (React) is rebuilt as `apps/studio`.
  Libs and gateway are untouched — the OpenAPI contract is the only
  interface, and it does not change.

## The layout

```
┌────────────────────────────────────────────────────────────────┐
│  ◉ workspace switcher      ⌘K command palette       🧠 model ⚙ │
├──────────┬─────────────────────────────────────────────────────┤
│ LAYERS   │                                                     │
│ tree     │                  MAP CANVAS (home)                  │
│ ▸ scenes │        MapLibre GL — no token, fully local          │
│ ▸ ET     │   base · raster scenes · products · GeoJSON · ROIs  │
│ ▸ docs   │                                                     │
│ ▸ ROIs   │   ┌───────────────────────────┐                     │
│          │   │ AGENT RAIL (collapsible)  │ ← streaming chat,   │
├──────────┴───┤ plan → tool cards → cited │   tool trace,       │
│ ✦ draw ROI   │ answer                    │   playbooks         │
└──────────────┴───────────────────────────┴─────────────────────┘
```

The map is the home page. Everything else is a page or a rail.

## The six surfaces

| # | Page | What the user does | Powered by |
|---|------|--------------------|------------|
| 1 | **Map** | Toggle layers, zoom, draw ROI (polygon/bbox/parcel). ROI is a first-class object: named, saved, reused. | MapLibre + gateway `/files` + GeoJSON |
| 2 | **Acquire** (data engine) | Pick sensor + date range for the current ROI → scene search results → click Download. Jobs run server-side with live progress. | `data_engine` fetcher as gateway job |
| 3 | **Resources** | Drag-drop PDFs/GeoTIFFs/GeoJSON. Watch ingest + indexing progress. Browse collections, index stats. | `geomemory` ingest jobs |
| 4 | **Ask** | Search and grounded QA. Citation chips open the exact segment on a split view. Abstention is a designed state, not an error. | `geomemory` search/QA |
| 5 | **Agent** | Streaming chat with visible plan and tool cards. The agent can draw ROIs, download data, ingest resources, train models — everything pages can do. | `geoagent` + tool registry |
| 6 | **Training Lab** | Review queue (accept/reject) → one-click "Train now" → live metrics while `partial_fit` runs (seconds, CPU) → model versions with rollback. Predictions show confidence and abstention. | `geolearn` |

## The one API principle

**The UI is just another client. The agent is a peer client. Both consume
only the gateway.**

Agent tool ↔ page pairing:

| Agent tool | Same endpoint the page uses |
|---|---|
| `roi_create` | same route the Map page saves ROIs to |
| `data_download` | same job endpoint the Acquire page calls |
| `geo_ingest` | same ingest job as Resources |
| `geo_search` / `geo_ask` | same retrieval as Ask |
| `model_train` | same training job as Training Lab |

Consequence: anything a user can do by hand, the agent can do by tool —
with the same audit trail, the same citations, the same jobs. Nothing is
duplicated.

## Progress everywhere (the plumbing that exists)

- Long ops already return `202 {job_id}` → `GET /api/v1/jobs/{id}`.
- SSE already streams at `/api/v1/events`; the web client already
  invalidates caches from events.
- To add: `job.progress` events (0–100, stage, ETA) over SSE. Every page
  gets progress bars from one mechanism. Downloads report per-scene and
  per-band stages; ingest reports per-asset indexing; training reports
  batch number and accuracy.

## What makes downloads fast

1. Parallel band/asset fetches (bounded concurrency).
2. Streaming writes into the SHA-256 object store — no temp files.
3. Per-scene resumability: a failed band re-fetches alone.
4. COG output so the map previews tiles before full ingest finishes.
5. The map never blocks: scenes appear as layers the moment they land.

## The demo (the one that sells)

> *"Watch: I draw a field."* ROI appears, named `farm-42`.
> *"Download Landsat for July."* Progress bars fill; ET and NDVI layers
> fade in on the map.
> *"Why is the north pivot stressed?"* Cited answer, chips linking to
> segments and rasters.
> *"No — it's the irrigation schedule."* Feedback accepted. Training Lab
> shows the classifier update in two seconds. Next answer reflects it.

Sixty seconds, no cloud account, no data leaving the machine.

## Design principles (inherited + new)

1. **Citations or abstention** — unchanged, first-class in every surface.
2. **Map is home** — geospatial is the identity, not a feature.
3. **Progress is a right** — no blocking spinners; every long op streams.
4. **Agent parity** — agent tools and UI pages share one API.
5. **Local-first, hybrid compute** — remote LLM by default, GGUF offline.
6. **Frugal ML** — training happens on CPU in seconds, visible in the UI.

## Milestones

| Phase | Ships | Exit check |
|---|---|---|
| M1 | SvelteKit shell + map + layer tree + ROI draw | ROI saved and rendered from gateway |
| M2 | Acquire page + download jobs + `job.progress` SSE | Draw → download → layer on map, live progress |
| M3 | Resources + Ask + citation chips + abstention UI | 60s: ingest PDFs, get cited answer |
| M4 | Agent rail: streaming, tool cards, playbooks, agent parity | Agent does M2 + M3 via tools |
| M5 | Training Lab: review queue, train-now, versions | Feedback changes next prediction, visibly |

## Open questions

- Package name and app name (`GeoMind Studio` vs. product rename).
- Ship M1–M2 in `apps/studio` alongside the existing React web?
- Offline map basemap source (local vector tiles vs. OSM raster cache).
- ROI schemas: do parcels from `farms` become ROIs automatically?
