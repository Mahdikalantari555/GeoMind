# Tasks: split-workspace-facade

## 1. Extract mixins (code moves verbatim)

- [ ] 1.1 `workspace_collections.py` — CollectionsMixin
- [ ] 1.2 `workspace_ingest.py` — IngestMixin + parse/mime/chunk helpers
- [ ] 1.3 `workspace_search.py` — SearchMixin + _WorkspaceSearchAdapter
- [ ] 1.4 `workspace_qa.py` — QAMixin (ask/_persist_answer/get_turn)
- [ ] 1.5 `workspace_feedback.py` — FeedbackMixin
- [ ] 1.6 `workspace_assets.py` — AssetsMixin (incl. build/rebuild index)
- [ ] 1.7 `workspace_knowledge.py` — KnowledgeMixin (entities/candidates/
      proposals/traverse/timeline)
- [ ] 1.8 `workspace_models.py` — ModelsMixin (model hub surface)

## 2. Compose facade

- [ ] 2.1 `workspace.py`: `class Workspace(CollectionsMixin, ...)` keeps
      lifecycle + settings + shared helpers; `GeoMemory` unchanged
- [ ] 2.2 Shared-state annotations on mixins for mypy --strict

## 3. Verify

- [ ] 3.1 Full geomemory pytest suite green (no test edits needed)
- [ ] 3.2 ruff + mypy --strict green
- [x] 3.3 `wc -l core/workspace.py` < 400; no mixin > 700
