## 1. Add i18n keys to en.json and fa.json

- [ ] 1.1 Add `eval` namespace keys to `en.json`: `description`, `benchmarkPathPlaceholder`, `configPathPlaceholder`, `runButtonPending`, `runButtonText`, `successTitle`, and verify the file parses as valid JSON
- [ ] 1.2 Add the same `eval` namespace keys to `fa.json` with Persian translations and verify the file parses as valid JSON
- [ ] 1.3 Add `review` namespace keys to `en.json`: `pending`, `approved`, `rejected`, `candidatesHeading`, `allStates`, `noCandidates`, `scoreLabel`, `promoteToSupported`, `promoteToVerified`, `reject`, `proposalsHeading`, `noProposals`, `original`, `proposed`, `approve`, `exportHint`, `exportDataset`, `exporting`, `downloadStarted`, and verify JSON validity
- [ ] 1.4 Add the same `review` namespace keys to `fa.json` with Persian translations and verify JSON validity
- [ ] 1.5 Add `overview.noWorkspace` and `overview.noWorkspaceHint` keys to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.6 Add `agent.dismiss`, `agent.retry`, `agent.notReadyTitle`, `agent.notReadyBody`, `agent.errorWorkspace` keys to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.7 Add `doctor.loading`, `doctor.probing`, `doctor.nullValue` keys to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.8 Add `ingest.selectCollection`, `ingest.dismiss`, `ingest.retry` keys to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.9 Add `ask.modelLabel` key to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.10 Add `error.codeLabel` key to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.11 Add `maps.classLabel` key to `en.json` and `fa.json`; verify JSON validity
- [ ] 1.12 Verify `en.json` and `fa.json` have identical key paths by running a recursive key-diff script (or manual audit) and confirming zero mismatches

## 2. Wrap hardcoded strings in feature components

- [ ] 2.1 In `EvalPage.tsx`: wrap line 23 description, lines 30/36 placeholders, and line 46 button text in `t()` using the keys added in 1.1–1.2; verify the page renders the same text in en mode
- [ ] 2.2 In `ReviewPage.tsx`: wrap all hardcoded strings (lines 30–32, 36, 39–43, 46, 53, 58–60, 68, 69, 73, 75–76, 78, 85, 91, 95) in `t()` using the keys added in 1.3–1.4; verify both en and fa render correctly
- [ ] 2.3 In `OverviewPage.tsx`: wrap lines 44–45 hardcoded strings in `t()` using keys from 1.5; verify en/fa render correctly
- [ ] 2.4 In `AgentChatPage.tsx`: wrap lines 198, 202, 210–211 hardcoded strings in `t()` using keys from 1.6; verify en/fa render correctly
- [ ] 2.5 In `DoctorPage.tsx`: wrap lines 61, 124, 315 hardcoded strings in `t()` using keys from 1.7; verify en/fa render correctly
- [ ] 2.6 In `IngestPage.tsx`: wrap lines 119, 182, 215 hardcoded strings in `t()` using keys from 1.8; verify en/fa render correctly
- [ ] 2.7 In `AskPage.tsx`: wrap line 318 `model:` label in `t()` using key from 1.9; verify en/fa render correctly
- [ ] 2.8 In `ErrorBoundary.tsx`: wrap line 23 `code:` label in `t()` using key from 1.10; verify en/fa render correctly
- [ ] 2.9 In `MapsPage.tsx`: wrap line 125 `class` label in `t()` using key from 1.11; verify en/fa render correctly

## 3. Fix non-logical RTL Tailwind properties

- [ ] 3.1 In `SearchPage.tsx` line 329: replace `ml-1.5` with `ms-1.5` on the modality chip span; verify the chip renders with correct start-alignment in both en (LTR) and fa (RTL) modes

## 4. Build and test verification

- [ ] 4.1 Run `cd apps/web && pnpm lint` and confirm zero errors
- [ ] 4.2 Run `cd apps/web && pnpm build` and confirm the build succeeds with no type errors
- [ ] 4.3 Run `cd apps/web && pnpm test` and confirm all unit tests pass
- [ ] 4.4 Manually open the app in the browser, switch language to fa, and visually verify: Eval page, Review page, Overview (closed state), Agent Chat (no-workspace state), Doctor page, Ingest page (invalid-collection state), Ask page, Maps page — all render in Persian without bare English strings
- [ ] 4.5 Switch back to en and confirm no visual regression from the original English UI
