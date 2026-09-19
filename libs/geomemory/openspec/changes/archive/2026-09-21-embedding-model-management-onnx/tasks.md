## 1. Lib — ONNX embedder + hub

- [x] 1.1 Create `libs/geomemory/src/geomemory/embeddings/onnx_text.py` (`OnnxTextEmbedder`: tokenizer+session, mean pool, L2 norm, `space_id=text.onnx.*`, e5 prefix). Add `geomemory[onnx]` extra.
- [x] 1.2 Extend `WorkspaceSettings` (`onnx_model_name`, `embedding_backend` allow `onnx`) + `embeddings/factory.py` routing + `core/config.ENV_OVERRIDES` for `GEOMEMORY_ONNX_MODEL`
- [x] 1.3 Create `embeddings/hub.py` (`EmbeddingModelHub.scan`, priority roots including `/mnt/data/LocalAI/Models/Embedding`, `download` with `huggingface_hub.snapshot_download`, progress callback, file lock). Unit tests for scan+offline guard.
- [x] 1.4 Auto-download wiring in `SentenceTransformerEmbedder._load` + `OnnxTextEmbedder._load` + `services/index_service.py` (attempt inline download when offline false else 503)

## 2. Server — model management API

- [x] 2.1 Add `server/src/geofront_api/routers/models.py`: `GET /models`, `POST /models/download` (202 job), `GET /models/{id}/status`. Wire `jobs` + SSE. Tests for list/download 202+progress, validation.
- [x] 2.2 Extend `routers/workspace.py` settings to accept `embedding_backend`/`st_model_name`/`onnx_model_name` with 422 `available`; extend `routers/index.py` to trigger auto-download fallback before build; extend `routers/doctor.py` `diagnostics.embedding` summary.

## 3. Web — settings embeddings + index hub

- [x] 3.1 Settings page: embeddings subsection (backend select, model picker from `GET /models`, `space_id` + size badges, Download button → `POST /models/download` → job progress bar, offline guard disabled state). `PUT /settings` wiring + `pnpm gen:api`.
- [x] 3.2 Index page: hub list table with per-row Download + progress, active backend/model banner, Build/Rebuild buttons that gracefully trigger auto-download when missing.
- [x] 3.3 Doctor page: embedding row (hub_count, active_model, fallback status) in diagnostics section.

## 4. Verification

- [x] 4.1 Lib: `conda run -n geospatial pytest libs/geomemory/tests/unit/test_embeddings.py libs/geomemory/tests/unit/test_embedding_auto_download.py libs/geomemory/tests/unit/test_provider.py -q` → 18 passed; `ruff check` + `mypy --strict` on onnx_text.py, hub.py, factory.py → clean.
- [x] 4.2 Server: `conda run -n geospatial pytest server/tests/test_models.py server/tests/test_index_auto_download.py -q` → 8 passed.
- [x] 4.3 Web: `pnpm lint` → 0 errors; `pnpm build` → success; `pnpm test` → 34 passed. Schema already current (models endpoints present in schema.d.ts).
