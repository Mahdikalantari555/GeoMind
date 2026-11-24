# Tasks — ship-and-measure-agent

> Status: All tasks delivered 2026-11-24. Docker smoke test could not run in this environment (container registry 403); `docker compose config` is green and the Studio image is buildable by the operator. Vision Studio view and MCP transport deliberately deferred (ADR 0003/0004).

Verification gates:
- `docker compose config` and a Docker smoke test (if Docker is available);
- `conda run -n geo pytest server/tests -q`;
- `cd apps/studio && pnpm.cmd check && pnpm.cmd test && pnpm.cmd build`.

## 1. Docker ships Studio (F-097)

- [x] 1.1 Add a `studio` service: multi-stage Vite single-file build → nginx
      with an `/api` proxy to the gateway; keep single uvicorn worker. (F-097)
- [x] 1.2 Make `studio` the default demo; move `web` behind a `reference`
      profile; update `README.md` quickstart/URLs. (F-097)
- [x] 1.3 `docker compose config` green; smoke test the Studio page + `/health`
      if Docker is available (note in the audit report if not). (F-097)

## 2. Publish the benchmark baseline (F-094)

- [x] 2.1 Freeze corpus slice, seeds and metric definitions; run the existing
      benchmark tooling; record the protocol. (F-094)
- [x] 2.2 Publish `docs/benchmarks/report.md`: retrieval-parity ablation
      (nDCG@10, MRR), abstention precision/recall, 100 % citation correctness
      as a machine-enforced pytest. (F-094)
- [x] 2.3 Add a README results table and wire the `regression-tracking` hook;
      archive `publish-agent-baseline` when the gate passes. (F-094)

## 3. Live agent chat (F-095)

- [x] 3.1 Define session/conversation-ID handoff and tool-card rendering from
      the existing `/agent/chat` SSE event names. (F-095)
- [x] 3.2 Implement the live path behind a flag; retire the scripted AgentRail
      path; add e2e coverage. (F-095)
- [x] 3.3 Complete and archive `add-studio-knowledge-agent`. (F-095)

## 4. Vision-search spike (F-096)

- [x] 4.1 Implement the tiles-to-embedding bridge against an existing
      workspace using `POST /images/search` and the ONNX embeddings. (F-096)
- [x] 4.2 Validate retrieval quality on `sample/`; decide tile vs scene
      granularity; write a decision record. (F-096)
- [x] 4.3 If quality is credible, define the Studio view as a follow-up; if
      not, STOP and report rather than committing to UI work. (F-096)

## 5. Learning-loop and MCP exposure spike (F-098)

- [x] 5.1 Decide which of `geo_record_feedback`, `geo_review_queue`, `geo_review`,
      `geo_export_dataset`, `geo_export_runs` ship in the spine; thin-wrap the
      existing geomemory/geolearn facades and add tests. (F-098)
- [x] 5.2 Decide whether `geoagent mcp` is in scope; defer transport until
      confirmed, and cap the tool manifest per `tool-registry` spec. (F-098)

## 6. Final gate

- [x] 5.1 All commands above green; update `tasks/todo.md` checkboxes and the
      CHANGELOG/release notes; no archived copies left in two places.
