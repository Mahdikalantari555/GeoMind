# GeoMind — Charter

> What GeoMind is, what it is not, and the order in which it grows.
> Status: spine locked 2026-11-21 — **the data-sovereign agent** (answers
> cite or abstain; feedback becomes training; data never leaves the
> machine). Owner: Mahdi Kalantari.

## Vision

A **data-sovereign AI platform for remote sensing research**: your knowledge
— documents, rasters, feedback — stays on your machine, while compute is
pluggable: a remote OpenAI-compatible LLM API **by default** (e.g. Kilo
gateway), local GGUF models when you need full offline. Citation-grounded
answers over your own data, with a feedback loop that turns researcher
judgment into training data.

GeoMind is the umbrella: the memory engine, the agent SDK, the algorithm
libraries, the gateway server, and the apps assembled on top. The name also
nods to foundation models — the platform is designed around small, local
foundation-model embedders (nomic, OlmoEarth) and their future RS kin.

## Layer model

```
┌────────────────────────────────────────────────────────────┐
│ APPS        web SPA · CLI · (future) MCP server · notebooks│
├────────────────────────────────────────────────────────────┤
│ GATEWAY     GeoMind/server — FastAPI · /api/v1            │
│             composes all libs; apps consume ONLY this      │
├────────────────────────────────────────────────────────────┤
│ APPLICATION libs/geoagent (SDK)      · libs/data_engine    │
│             agent framework · tools · playbooks · ET      │
│             model (METRIC ETa)                            │
├────────────────────────────────────────────────────────────┤
│ LEARNING    libs/geolearn — online learning,              │
│             incremental training, replay buffer           │
│             (future) GeoSynth — synthetic EO data         │
├────────────────────────────────────────────────────────────┤
│ MEMORY      libs/geomemory — knowledge store, hybrid       │
│             search, citations, feedback/review queue       │
├────────────────────────────────────────────────────────────┤
│ MODELS      (future) GeoModels — model registry/zoo:       │
│             GGUF LLMs, embedders, RS foundation models     │
├────────────────────────────────────────────────────────────┤
│ STORAGE     SQLite (FTS5 · RTree · WAL) + content-         │
│             addressed object store (SHA-256)               │
└────────────────────────────────────────────────────────────┘
```

**The one architectural rule:** dependencies point strictly downward.
Apps → Gateway → application/learning libs → memory → models → storage.
Apps never import libs directly; libs never import upward.

> **Current implementation note:** GeoLearn now exists as a versioned library
> (`libs/geolearn/`), and data_engine (the METRIC ETa algorithm library) is
> integrated into the application layer. The CHARTER's layer model describes
> the intended direction; `docs/ARCHITECTURE.md` records the actual dependency
> graph and identifies any deviations (e.g., geoagent importing geolearn
> tools, geolearn reading geomemory via raw SQLite).

## Core values

1. **Local data, hybrid compute** — workspaces and knowledge never leave the
   user's machine; the LLM is pluggable, remote API by default, local GGUF as
   offline fallback. `offline: true` flips fully local (blocks API backend).
2. **Frugal by design** — local embedders stay CPU-friendly (no GPU needed);
   compute can scale up to hosted APIs without moving the data.
3. **Citations or abstention** — answers cite segments with locators, or
   say nothing. No silent hallucination. Provenance chain:
   `answer → citation → segment → asset_revision → objects/<sha256>`.
4. **The feedback loop is the product** — search/QA feedback → review queue →
   exported datasets → GeoLearn training → better answers. This loop is the
   platform's differentiator vs. generic RAG tools.
5. **Framework + case studies** — libs stay domain-neutral; domain logic
   (sugarcane stress, ET, farms) lives in case studies and agent apps.

## Roadmap — now vs. later

| Phase | Scope |
|---|---|
| **Now** | Agent spine: publish benchmark numbers (retrieval parity · abstention quality · 100% citation correctness — `publish-agent-baseline`) · agent playbooks-copilot · dual-mode recall QA · Studio knowledge agent · training-lab feedback loop. ETa pilot = the demo case study |
| **Next** | GeoLearn hardening · GeoModels registry · MCP server app · open-source release (docs, install story, plugin story) |
| **Later** | GeoSynth · notebooks app · hosted/packaged product |

## What GeoMind is NOT

- Not a SaaS — no multi-tenant hosting, no auth beyond a local dev token.
- Not a fat meta-package — each lib is independently versioned and pinned.
- Not a data lake — workspaces are filesystem artifacts, not services.

## Naming

`GeoMind` = the platform/monorepo. Libs keep their own identities
(`geomemory`, `geoagent`, `data_engine`/`metric_et`, `geolearn`). Before any
public release: check GitHub/PyPI for name collisions.