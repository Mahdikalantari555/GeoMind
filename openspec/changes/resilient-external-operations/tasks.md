## 1. Dependency preparation

- [ ] 1.1 Add `tenacity>=8.0` to `libs/geoagent/pyproject.toml` `[project].dependencies` and to `libs/data_engine/pyproject.toml` `[project].dependencies`, then run `conda run -n geospatial pip install -e libs/geoagent -e libs/data_engine` and verify `import tenacity` succeeds in the env
- [ ] 1.2 Confirm no existing tenacity usage collides by running `grep -rn "import tenacity\|from tenacity" libs/geoagent/src libs/data_engine/src` — expect zero matches

## 2. LLM backend retries

- [ ] 2.1 In `libs/geoagent/src/geoagent/llm/openai_compat.py`, wrap the `urlopen` + response-parsing body inside a `@retry` decorator that stops after 3 attempts, waits exponentially (multiplier 1 s, min 1, max 30), and retries on `urllib.error.HTTPError` with code 429 or 503, plus `urllib.error.URLError`; verify via a unit test that mocks `urlopen` to raise 429 twice then succeed
- [ ] 2.2 Ensure retry exhaustion raises `LLMError` (not `RetryError` leaking to callers) — the decorator's `retry_error_callback` or a try/except around it should translate; verify the existing `test_llm_error_codes` or similar test still passes after wrapping
- [ ] 2.3 Add `llm_retry_max_attempts` and `llm_retry_base_delay_s` to `AgentSettings` (or an equivalent provider config model) with defaults 3 and 1.0; verify via a unit test that overriding these changes the retry count observed in a mocked backend

## 3. Weather API retries

- [ ] 3.1 In `libs/data_engine/src/data_engine/io/dynamic_weather_fetcher.py`, wrap the `requests.get` call in a tenacity `@retry` covering HTTP 429/502/503/504 and `requests.RequestException`; verify via a unit test using `responses` or `httpretty` that a 429 followed by 200 returns data without raising
- [ ] 3.2 Verify that exhausted retries return `None` and emit a `logger.warning` (preserve the existing silence contract for failed weather); add or update a test that drives three 503s and asserts `None` return and a single warning log record
- [ ] 3.3 Ensure per-attempt `timeout=30` is still passed through to each `requests.get` call; verify by inspecting the mock call args in the test

## 4. STAC fetcher retries

- [ ] 4.1 In `libs/data_engine/src/data_engine/io/planetary_computer_fetcher.py`, wrap `self.client.search(...)` and any download calls in tenacity `@retry` decorators matching the same transient codes; verify via a unit test that a 429 on search is retried and eventual success returns items
- [ ] 4.2 Verify that non-transient errors (400, 404) are raised immediately without retry; add a test confirming one call and a 404 exception
- [ ] 4.3 Confirm that the `search_scenes` return type and item schema are unchanged after retry wrapping — run the existing data-engine tests (`pytest libs/data_engine/tests -q`) and assert no regressions

## 5. SQLite busy_timeout increase

- [ ] 5.1 Change `"PRAGMA busy_timeout=5000"` to `"PRAGMA busy_timeout=30000"` in `libs/geomemory/src/geomemory/storage/database.py`; verify by opening a connection in a test and asserting `conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000`
- [ ] 5.2 Run `pytest libs/geomemory/tests -q` to confirm no regressions in WAL, foreign-keys, or migration tests
- [ ] 5.3 Verify that the existing `test_workspace_lifecycle` pre-existing failure is unaffected (it is outside our scope)

## 6. Daemon-thread leak fix

- [ ] 6.1 In `libs/geoagent/src/geoagent/registry.py`, replace the current `worker.join(tool.timeout_s)` + `if worker.is_alive(): return timeout_result` with a two-phase join: `worker.join(timeout=tool.timeout_s + 0.5)`, then check `is_alive()` and log a warning if still alive (the thread is daemon and will be reclaimed on exit)
- [ ] 6.2 Write a unit test that runs a tool whose body sleeps longer than `tool.timeout_s`, asserts `execute()` returns `ToolResult(status="timeout")`, and then asserts `threading.active_count()` has not increased compared to before the call
- [ ] 6.3 Run repeated timed-out executions (e.g., 10 iterations) and verify no monotonic thread growth; use `threading.enumerate()` snapshot comparison

## 7. Integration and lint checks

- [ ] 7.1 Run `conda run -n geospatial ruff check libs/geoagent/src libs/data_engine/src libs/geomemory/src` from repo root and fix any violations
- [ ] 7.2 Run `conda run -n geospatial mypy --strict libs/geoagent/src` and `mypy --strict libs/data_engine/src` and `mypy --strict libs/geomemory/src`; fix type errors introduced by the new imports/decorators
- [ ] 7.3 Run the full gateway test suite `conda run -n geospatial pytest server/tests -q` to confirm no cross-cutting regressions
- [ ] 7.4 Regenerate the web API client (`cd apps/web && pnpm gen:api`) only if any error envelope changed; otherwise skip and document why
- [ ] 7.5 Run `pnpm lint && pnpm build` in `apps/web` to confirm the SPA still compiles

## 8. Documentation and tracking

- [ ] 8.1 Update `tasks/todo.md` checkboxes to reflect completion status of each task above
- [ ] 8.2 Add a short note in `docs/current-state/tech-debt.md` (or the relevant gap-analysis section) acknowledging that retry logic is now present, reducing the open H2/H4 findings from the audit
