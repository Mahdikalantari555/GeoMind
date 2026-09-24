## 1. Dynamic Paths and Ingest Serialization

- [ ] 1.1 Verify dynamic workspace root resolution in `server/src/geofront_api/state.py` and test isolation in `server/tests/conftest.py` with `conda run -n geospatial pytest server/tests/test_workspace.py`
- [ ] 1.2 Verify `EmbeddingModelHub` scan root removal of hardcoded `/mnt/data` in `libs/geomemory/src/geomemory/embeddings/hub.py` with `conda run -n geospatial pytest libs/geomemory/tests/unit/test_embedding_auto_download.py`
- [ ] 1.3 Fix multipart header generation in `apps/web/src/api/client.ts` to omit `Content-Type` for `FormData` and verify with `cd apps/web && pnpm lint && pnpm test`

## 2. Static Contract & API Audit

- [ ] 2.1 Audit all client endpoints in `apps/web/src/api/` against `server/src/geofront_api/routers/` (checking parameter names, schemas, query parameters, and HTTP methods) and fix any mismatches
- [ ] 2.2 Run OpenAPI client generator `pnpm gen:api` in `apps/web` and compile types with `pnpm build` to verify zero type errors

## 3. UI Interactive Component & Form Audit

- [ ] 3.1 Audit Ingest and Assets pages (`IngestPage.tsx`, `AssetsPage.tsx`): test file upload dropzone, collection selector, index-after toggle, and job status polling
- [ ] 3.2 Audit Workspace and Settings pages (`OverviewPage.tsx`, `SettingsPage.tsx`, `DoctorPage.tsx`): test workspace create/open/close, LLM key updates, and diagnostics reporting
- [ ] 3.3 Audit Search and Ask pages (`SearchPage.tsx`, `AskPage.tsx`): test text/image modality switches, spatial bbox filter, and citation / abstention cards
- [ ] 3.4 Audit Agent, Playbooks, and Knowledge pages (`AgentChatPage.tsx`, `ToolsPage.tsx`, `PlaybooksPage.tsx`, `CollectionsPage.tsx`, `FarmsPage.tsx`): test chat input, tool execution, and collection CRUD

## 4. End-to-End Verification & Automated Testing

- [ ] 4.1 Run full Python backend test suite (`conda run -n geospatial pytest server/tests -q`) and verify 100% pass rate
- [ ] 4.2 Run full web test suite (`pnpm test` and `pnpm build` in `apps/web`) and verify zero failures
- [ ] 4.3 Execute end-to-end integration test with Playwright covering workspace creation, file ingestion, search, and agent chat
