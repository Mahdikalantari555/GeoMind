# Proposal: split-workspace-facade

> Lib-level change. Lives in `libs/geomemory/openspec/changes/` per the
> per-lib openspec ownership rule (root AGENTS.md).

## Why

`geomemory/core/workspace.py` is a 1,947-line god-object (ARCHITECTURE.md
risk #4): lifecycle, collections, ingest, search, QA, feedback, assets,
knowledge, model hub, and traversal all live in one class. Every consumer
funnels through it, so every feature grows it further and every refactor
risks touching everything. It is the single point of architectural
fragility in the lib.

## What Changes

- Split `Workspace` into focused **mixin modules** under `core/` — code
  moves verbatim; `self`-shared state stays shared; the facade class
  composes them:
  - `workspace_collections.py` — `CollectionsMixin` (create/list/get/archive)
  - `workspace_ingest.py` — `IngestMixin` (+ module helpers `_detect_mime`,
    `_kind_for_mime`, `_chunk_document`, `_parse_spatial_source`)
  - `workspace_search.py` — `SearchMixin` (+ `_WorkspaceSearchAdapter`)
  - `workspace_qa.py` — `QAMixin` (`ask`, `_persist_answer`, `get_turn`)
  - `workspace_feedback.py` — `FeedbackMixin` (feedback events, review,
    dataset export, benchmark, pipeline stats)
  - `workspace_assets.py` — `AssetsMixin` (list/inspect/stats/index
    manifest/build/rebuild, image index)
  - `workspace_knowledge.py` — `KnowledgeMixin` (entities, profiles,
    research timeline, candidate memories, proposals, traverse)
  - `workspace_models.py` — `ModelsMixin` (embedding model hub surface)
- `workspace.py` keeps: `Workspace.__init__` + lifecycle + settings +
  shared private helpers (`_workspace_id`, `_asset_by_id`,
  `_revision_by_id`, `_segments_for_revision`, `_save_retrieval_run`,
  `_load_json`), composes the mixins, and still exports `GeoMemory`.
- **Zero public API change.** `geomemory.__init__` imports, method names,
  signatures, events, and DB behavior are identical. The only consumer-
  visible difference: internals live in `geomemory.core.workspace_*`
  modules.

## Non-goals

- No behavior changes, no new features, no signature changes.
- No extraction into services (a composition rewrite is a later change;
  mixins are the zero-risk mechanical step that kills the god file).

## Impact

- **geomemory:** `core/workspace.py` shrinks to ~350 lines; 8 new modules
  carry the moved groups. Shared attributes referenced by mixins are
  declared as annotations so mypy --strict stays green.
- **Consumers:** none — import surface (`geomemory.GeoMemory`) unchanged.
- **Risk control:** full geomemory suite (76 test files) must pass
  unchanged; ruff + mypy --strict green.
