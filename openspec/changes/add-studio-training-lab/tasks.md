# Tasks: add-studio-training-lab

## 1. Review queue (studio-review-queue)

- [x] 1.1 Pending list with source context, evidence segments, proposed
      correction; provenance chain links (answer → citation → segment → asset)
- [x] 1.2 Accept/reject with optional note; bulk select-and-act; append-only
      event recording with actor + timestamp
- [x] 1.3 Per-key readiness counts with Train-now link at threshold
- [x] 1.4 Unit tests: queue state, bulk actions, readiness counts

## 2. Training lab (studio-training)

- [x] 2.1 Train-now gateway job (threadpool over geolearn public API) with
      batch/sample/accuracy progress via `job.progress` SSE
- [x] 2.2 Live training metrics rendering; UI stays interactive during runs
      (Studio store subscribes to the real job; version list refreshes
      from /models/versions)
- [x] 2.3 Version list (timestamp, samples, accuracy) + one-click rollback
      with audit record
- [x] 2.4 Cold-start transparency state (<30 samples → NN fallback notice
      with samples-to-graduation count)
- [x] 2.5 Prediction surfacing: confidence always shown; below-threshold
      renders as explicit abstention
- [x] 2.6 Unit tests: progress rendering, version/rollback state, abstention
      renderer

## 3. Server

- [x] 3.1 Training job route wired to geolearn facade; progress reporting
      adopted; rollback endpoint with audit
- [x] 3.2 Server tests: job lifecycle, progress events, rollback audit;
      ruff + mypy --strict + pytest green
- [x] 3.3 Regenerate OpenAPI schema

## 4. Validation

- [x] 4.1 Full-loop manual scenario: feedback accepted → train now → metrics
      live → next prediction changes visibly (with confidence shown)
- [x] 4.2 Studio + server gates all green; e2e suite still deferred (tracked)
