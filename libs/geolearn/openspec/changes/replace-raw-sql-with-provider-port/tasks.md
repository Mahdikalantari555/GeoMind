# Tasks: replace-raw-sql-with-provider-port

## 1. Port

- [ ] 1.1 Add `geolearn/ports.py`: `CandidateLike` and
      `CandidateMemoryProvider` Protocols (structural, runtime_checkable)
- [ ] 1.2 `TrainingPipeline.__init__(geolearn_dir, candidate_source)` —
      provider only; delete `_get_workspace` soft import,
      `_get_geomemory_db_path`, and the raw-SQL fallback block

## 2. Progress

- [ ] 2.1 `progress_cb` kwarg on `train_on_feedback`/`run`
      (`(key, batch_index, batch_total)`); callback errors swallowed+logged

## 3. Callers

- [ ] 3.1 `geoagent/tools/geolearn_tools.py`: facade from
      `memory_tools.get_memory()`; fallback `GeoMemory.open()` in geoagent
- [ ] 3.2 Gateway training route passes `state.require_workspace()`
      (lands with root change `add-studio-training-lab`)

## 4. Tests

- [ ] 4.1 Rewrite `test_pipeline_training` raw-SQL fixture → fake provider
- [ ] 4.2 New test: provider=None → pending 0, train no-op
- [ ] 4.3 New test: progress_cb receives (key, i, n) and survives raising cb
- [ ] 4.4 Import audit: geolearn src has no `geomemory` / `sqlite3` on
      geomemory paths (grep-based test)

## 5. Quality

- [ ] 5.1 pytest + ruff + mypy --strict green in geolearn and geoagent
- [ ] 5.2 Update docs/ARCHITECTURE.md + docs/SUMMARY.md deviation notes
