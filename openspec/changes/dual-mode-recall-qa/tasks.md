# Tasks: dual-mode-recall-qa

- [ ] 1. Backend Recall Mode Verification
  - [ ] 1.1 Verify `Workspace.ask(mode="recall")` properly surfaces citation locators and segments.
  - [ ] 1.2 Ensure gateway endpoint `/api/v1/ask` returns full citation metadata and provenance fields.
- [ ] 2. Split Search & QA Interface (`uBfSK.jpg`)
  - [ ] 2.1 Refactor `AskPage.tsx` and `SearchPage.tsx` into a cohesive split view layout.
  - [ ] 2.2 Build `SearchHitCard.tsx` with similarity score badge, sensor tag, and mini polygon preview.
  - [ ] 2.3 Build `QAResultCard.tsx` with confidence indicator, copy button, and mode switcher (`Fast` / `Slow`).
- [ ] 3. Citation & Provenance Drawer
  - [ ] 3.1 Build inline citation chip parser for answer markdown text (`[1]`, `[2]`).
  - [ ] 3.2 Build `ProvenanceDrawer.tsx` displaying segment text, asset metadata, and SHA-256 hash.
- [ ] 4. Abstention & Empty States
  - [ ] 4.1 Implement `AbstentionBanner.tsx` with diagnostic reasons and recommended next steps.
  - [ ] 4.2 Add query presets and suggested prompt chips for quick exploration.
- [ ] 5. Testing & Verification
  - [ ] 5.1 Unit tests for citation parsing and drawer state management.
  - [ ] 5.2 E2E test verifying query → fast recall → citation click → drawer open.
