# Proposal: add-studio-training-lab

## Why

The feedback loop is the platform's differentiator (CHARTER value #4), but
today it is plumbing with no face. This change gives the loop a home in
GeoMind Studio: a review queue that turns researcher judgment into training
data, and a training view where light models learn visibly — on CPU, in
seconds — with versions, rollback, and calibrated confidence.

## What Changes

- **Review queue**: pending feedback items (answer/candidate-memory
  accept/reject) with bulk actions; each decision records provenance.
- **Train now**: a gateway training job over `geolearn` (per `(crop_type,
  region)` classifiers, `partial_fit`) reporting live progress (batch count,
  accuracy) via `job.progress` SSE.
- **Model versions**: list with accuracy summaries, rollback action; cold-start
  state (<30 samples → NN fallback) shown explicitly.
- **Prediction surfacing**: predictions displayed with confidence and
  abstention (below-threshold = explicit abstain), never bare class labels.
- Training runs entirely on CPU; the UI stays responsive (background job,
  not a blocked tab).

## Capabilities

### New Capabilities
- `studio-review-queue` — feedback review UX with provenance.
- `studio-training` — training job UX, versions, rollback, prediction
  surfacing.

## Impact

- **Server:** training job orchestration (threadpool over existing geolearn
  facades); job progress adoption. OpenAPI regenerated.
- **Libs:** none — geolearn's public surface is already sufficient.
- **Studio:** Training Lab page replacing the placeholder nav entry.

## Dependencies

- Builds on `add-svelte-studio-app` (shell, SSE) and
  `add-studio-knowledge-agent` (feedback sources from Ask/agent flows).
- Known deviation to respect: geolearn currently reads `candidate_memory`
  via raw SQLite (documented controlled coupling). This change consumes
  geolearn's public API only and does not deepen that coupling.
