# Proposal: integrate-studio-frontend

## Why

The GeoMind Studio product vision (`research/startup-vision/VISION.md`) requires "One app, one map, one loop":
1. **Draw → Download** (MapLibre ROI draw → STAC scene search → clipped COG download with live SSE progress).
2. **Ask → Cite** (Grounded Q&A over ingested documents and rasters with span citation chips, provenance drawer, and designed abstention).
3. **Correct → Learn** (Feedback review queue → 1-click CPU `partial_fit` online adaptation with `geolearn` in seconds → model versions with rollback).

The production frontend implementation in `apps/studio/` delivers all six vision surfaces:
- **Map Canvas Home** (`/`): MapLibre GL instance, raster layers (NDVI, ETa, True Color, Hillshade), vector basin/parcel boundaries, BBox/Polygon ROI drawing with area/centroid calculations.
- **Acquire** (`/acquire`): Scene finder (Landsat 8/9, Sentinel-2), date/cloud filters, quicklook previews, step-by-step download queue reporting live progress (`job.progress`).
- **Resources** (`/resources`): Drag-and-drop ingest for PDFs, GeoTIFFs, GeoJSON, CSVs with modality-isolated embedding pipelines and SHA-256 content addressing.
- **Knowledge** (`/knowledge`): Hybrid/Semantic/Keyword search, grounded QA with confidence ring and citation chips, split-screen provenance inspection drawer, strict abstention state.
- **Training Lab** (`/training`): Review queue (accept/reject/correct), 1-click CPU `partial_fit` online learning, live accuracy delta metrics, checkpoint rollback.
- **Agent Rail**: Collapsible docked side rail (`Ctrl+B`) with streaming text, inspectable tool cards (`hybrid_search`, `roi_create`, `metric_compute`), and playbooks.
- **Ops & Settings**: Real-time job queues (retry/cancel), storage quotas, log stream, local GGUF/Ollama endpoints, display density, and bilingual LTR/RTL switching (English/Persian).

`apps/web` (the legacy React app) remains untouched in the repository.

## What Changes

- Replace the incomplete Svelte prototype in `apps/studio/` with the production React 19 + MapLibre + Tailwind CSS v4 Studio frontend.
- Wire API client (`src/lib/api.ts`) to the FastAPI gateway at `/api/v1` with Vite proxy on port 5174.
- Support dual operation mode:
  1. Offline mode: Fully functional out of the box with bundled Karkheh Basin sample data.
  2. Live gateway mode: Activated via `VITE_GEOMIND_API` (or Vite proxy), streaming live jobs via EventSource (`/jobs/{id}/events`).
- Ensure full Persian (فارسی) RTL support with logical CSS properties (`ms-*`, `me-*`, `start-*`, `end-*`) while keeping cartographic MapLibre viewport strictly geographic LTR.

## Capabilities

### New Capabilities
- `studio-frontend-core` — App shell, Topbar, command palette (`⌘K`), bilingual RTL/LTR engine, responsive drawer/rail system.
- `studio-maplibre-roi` — MapLibre GL map, procedural raster shaders/ramps, GeoJSON parcels/basins, interactive ROI drawing tools (BBox, polygon).
- `studio-acquire-flow` — STAC scene search, clipped COG download workflow, stepwise progress display.
- `studio-ingest-resources` — Multi-format file drop zone, pipeline visualizer, collection table with SHA-256 fingerprints.
- `studio-grounded-knowledge` — Hybrid retrieval, citation chip linking, provenance drawer, confidence gauge, abstention state.
- `studio-training-loop` — Prediction review queue, 1-click CPU online learning, version history, rollback.
- `studio-agent-rail` — Streaming chat rail, visible tool execution trace, agent parity (creating ROIs and triggering jobs).

### Modified Capabilities
- `apps/web` — Marked frozen; remains untouched as reference until studio testing is complete.

## Impact

- **Apps**: `apps/studio/` is now a self-contained, high-performance React 19 + MapLibre SPA that builds cleanly to a single bundle or static distribution.
- **Server**: Existing gateway endpoints (`/api/v1/health`, `/data/search`, `/data/download`, `/knowledge/ask`, `/models/train`, `/jobs/{id}/events`) are mapped directly.
- **Docs**: Update `docs/SPEC_WEB.md` and `AGENTS.md` to reference the active Studio architecture.
