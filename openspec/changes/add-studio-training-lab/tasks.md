# Tasks: add-studio-training-lab

## 1. Review queue (studio-review-queue)

- [ ] 1.1 Pending list with source context, evidence segments, proposed
      correction; provenance chain links (answer → citation → segment → asset)
- [ ] 1.2 Accept/reject with optional note; bulk select-and-act; append-only
      event recording with actor + timestamp
- [ ] 1.3 Per-key readiness counts with Train-now link at threshold
- [ ] 1.4 Unit tests: queue state, bulk actions, readiness counts

## 2. Training lab (studio-training)

- [ ] 2.1 Train-now gateway job (threadpool over geolearn public API) with
      batch/sample/accuracy progress via `job.progress` SSE
- [ ] 2.2 Live training metrics rendering; UI stays interactive during runs
- [ ] 2.3 Version list (timestamp, samples, accuracy) + one-click rollback
      with audit record
- [ ] 2.4 Cold-start transparency state (<30 samples → NN fallback notice
      with samples-to-graduation count)
- [ ] 2.5 Prediction surfacing: confidence always shown; below-threshold
      renders as explicit abstention
- [ ] 2.6 Unit tests: progress rendering, version/rollback state, abstention
      renderer

## 3. Server

- [ ] 3.1 Training job route wired to geolearn facade; progress reporting
      adopted; rollback endpoint with audit
- [ ] 3.2 Server tests: job lifecycle, progress events, rollback audit;
      ruff + mypy --strict + pytest green
- [ ] 3.3 Regenerate OpenAPI schema

## 4. Validation

- [ ] 4.1 Full-loop manual scenario: feedback accepted → train now → metrics
      live → next prediction changes visibly (with confidence shown)
- [ ] 4.2 Studio + server gates all green; e2e suite still deferred (tracked)
