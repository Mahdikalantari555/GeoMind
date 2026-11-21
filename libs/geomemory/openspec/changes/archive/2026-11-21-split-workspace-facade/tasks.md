# Tasks: split-workspace-facade

> Bookkeeping note (2026-11-21): code verified in src — all eight mixins
> plus the composed facade exist; suite is CI-green (Windows-only env
> failures are pre-existing, tracked in tasks/todo.md). Boxes ticked
> retroactively. 3.2 is left open on purpose.

## 1. Extract mixins (code moves verbatim)

- [x] 1.1 `workspace_collections.py` — CollectionsMixin
- [x] 1.2 `workspace_ingest.py` — IngestMixin + parse/mime/chunk helpers
- [x] 1.3 `workspace_search.py` — SearchMixin + _WorkspaceSearchAdapter
- [x] 1.4 `workspace_qa.py` — QAMixin (ask/_persist_answer/get_turn)
- [x] 1.5 `workspace_feedback.py` — FeedbackMixin
- [x] 1.6 `workspace_assets.py` — AssetsMixin (incl. build/rebuild index)
- [x] 1.7 `workspace_knowledge.py` — KnowledgeMixin (entities/candidates/
      proposals/traverse/timeline)
- [x] 1.8 `workspace_models.py` — ModelsMixin (model hub surface)

## 2. Compose facade

- [x] 2.1 `workspace.py`: `class Workspace(CollectionsMixin, ...)` keeps
      lifecycle + settings + shared helpers; `GeoMemory` unchanged
- [x] 2.2 Shared-state annotations on mixins for mypy --strict

## 3. Verify

- [x] 3.1 Full geomemory pytest suite green (no test edits needed)
- [ ] 3.2 ruff + mypy --strict green
      (ruff green; mypy --strict has ~46 pre-existing errors in untouched
      files — tracked in tasks/todo.md, CI gates changed-files only)
- [x] 3.3 `wc -l core/workspace.py` < 400; no mixin > 700
