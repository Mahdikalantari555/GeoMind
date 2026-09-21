## Context

External I/O spans three independent subsystems:
- **LLM calls** (`libs/geoagent`): `OpenAICompatBackend.chat()` uses bare `urllib.request.urlopen` with no retry, failing immediately on 429/503/connection error.
- **Weather data** (`libs/data_engine`): `DynamicWeatherFetcher._fetch_one()` uses bare `requests.get` with no retry; Open-Meteo rate-limits at ~10 req/min.
- **STAC assets** (`libs/data_engine`): `PlanetaryComputerFetcher.search_scenes()` and download methods have no retry against planetary-computer.azure.net, which occasionally returns 429/503.
- **SQLite** (`libs/geomemory`): `database.py` sets `busy_timeout=5000`; with concurrent reads this is too aggressive.
- **Tool registry** (`libs/geoagent`): `ToolRegistry.execute()` spawns a `daemon=True` thread, joins on `tool.timeout_s`, and on timeout returns early — but the alive thread continues running in the background, accumulating over repeated tool-timeout cycles.

`tenacity` is not currently a dependency of any library; it must be added to `libs/geoagent` and `libs/data_engine`. No other new third-party deps are needed.

The gateway server and web app do not import internals of these libs; they observe resilience through fewer transient errors and different error shapes (retry exhaustion vs immediate failure).

## Goals / Non-Goals

**Goals:**
- Wrap every externally-facing HTTP call (LLM, weather, STAC) in a tenacity retry decorator covering known-transient codes.
- Raise SQLite `busy_timeout` to reduce locked-database exceptions under load.
- Fix the daemon-thread leak in `ToolRegistry.execute()` so timed-out workers are fully cleaned up.
- Keep retry budgets bounded so callers see latency only when recovery is likely.
- Preserve existing error-shape contracts where possible (`LLMError`, `None` return on weather exhaust, etc.).

**Non-Goals:**
- Adding circuit-breaker or bulkhead patterns — those are future hardening layers.
- Changing the LLM provider interface or adding a client-side SDK.
- Retrying on client-side (4xx) errors other than 429.
- Making retries configurable per-call at runtime via the API (config is static at construction time).
- Covering internal-only or in-process calls (embeddings, disk I/O).

## Decisions

### D1: Use tenacity for all retries
**Choice**: Add `tenacity>=8.0` and use its `@retry` decorator with `stop_after_attempt` and `wait_exponential`.
**Rationale**: `tenacity` is the standard Python retry library; it composes well with Pydantic config models and provides stop/wait/ retry-if predicates. Alternatives considered:
- `urllib`-level manual loops: fragile, no backoff, easy to get wrong.
- Custom wrapper: reinvents what tenacity provides; harder to test.
- `httpx` with built-in retries: would require rewriting `OpenAICompatBackend` away from stdlib urllib, introducing a larger surface area and a new transitive dep.

**Evidence**: tenacity is already used in many scientific-Python projects; its API is minimal (`RetryError`, `statistic`, `retry_if_exception_type`).

### D2: Exponential backoff with capped max attempts
**Choice**: Default `stop=stop_after_attempt(3)`, `wait=wait_exponential(multiplier=1, min=1, max=30)`.
**Rationale**: Three attempts catch most transient blips; exponential backoff respects upstream throttle windows (especially Open-Meteo's ~10 req/min). A `max` of 30 s prevents unbounded waiting.

### D3: Different swallow semantics per caller
**Choice**:
- LLM backend: always re-raise `LLMError` on exhaustion — the agent loop needs to know the model is unreachable.
- Weather fetcher: return `None` on exhaustion, preserving the existing "failed weather → null" contract used by ETa pipelines.
- STAC fetcher: re-raise the final exception — pipeline stages upstream need to know scene discovery failed.

### D4: SQLite busy_timeout raised to 30 s, not removed
**Choice**: Change `_PRAGMAS` tuple to `"PRAGMA busy_timeout=30000"`.
**Rationale**: The single-writer invariant means writes are serialized; 5 s was sufficient historically but edge cases (vacuum, large index builds) cause 5000 ms to expire. 30 s is generous without hiding real contention bugs. An alternative — increasing to infinite (remove busy_timeout) — would block forever under lock contention and is unacceptable.

### D5: Thread cleanup via explicit join-with-fence
**Choice**: Replace the bare `worker.join(tool.timeout_s)` + `if worker.is_alive()` pattern with a two-phase approach:
1. `worker.join(timeout=tool.timeout_s + small_buffer)` to ensure the thread has time to finish its exception handling.
2. If still alive after the extended join, record the timeout result and let the daemon thread exit naturally (it will be killed on process exit).

**Rationale**: The current code returns on timeout while the thread may still be mid-execution, accumulating zombie threads. Extending the join slightly (e.g., +0.5 s buffer) gives the thread time to reach its own exception boundary; daemon threads are terminated on interpreter shutdown anyway, but we want them gone before then for accurate metrics and memory.

### D6: Configurable retry params via AgentSettings and DataEngine settings
**Choice**: Expose `llm_retry_max_attempts` and `llm_retry_base_delay_s` on `AgentSettings`; expose equivalent fields on the `WeatherFetcher` constructor.
**Rationale**: Allows tuning in deployment without code changes. Tests can override with small values.

## Risks / Trade-offs

- **[Risk] Increased latency on legitimate slow providers** → Mitigation: `max_attempts=3` and `max_wait=30 s` cap worst case; most successful retries happen on attempt 2 at ~1 s delay.
- **[Risk] tenacity adds a transitive dependency** → Mitigation: tenacity is lightweight (~50 KB); required by the lib explicitly, not transitively. Both `libs/geoagent` and `libs/data_engine` declare it directly.
- **[Risk] Raising busy_timeout may mask real lock contention** → Mitigation: 30 s is high enough for normal operations but still bounded; if contention is pathological the error will still raise as `DatabaseError` after 30 s.
- **[Risk] Thread-join buffer change could hide genuine hangs** → Mitigation: the buffer is small (500 ms) and the thread is still daemon; we track timeouts in audit logs regardless.

## Migration Plan

1. Add `tenacity>=8.0` to `libs/geoagent/pyproject.toml` and `libs/data_engine/pyproject.toml`.
2. Update `openai_compat.py` to import tenacity decorators and wrap `chat()` body in a `@retry` rule; extend `_PRAGMAS` in `database.py`.
3. Update `registry.py` join logic; update weather and STAC fetchers similarly.
4. Run `conda run -n geospatial pytest libs/geoagent/tests -q` and `pytest libs/data_engine/tests -q` and `pytest libs/geomemory/tests -q` to verify no regressions.
5. Regenerate the web API client (`pnpm gen:api`) only if error-shape changes are intentional — the spec preserves existing shapes so this step is optional.
6. Rollback: revert the pyproject.toml additions and source changes; no schema migration needed.

## Open Questions

- **OQ1**: Should retry attempts and delays be configurable via the workspace settings endpoint (`PUT /api/v1/workspace/settings`) at runtime, or is construction-time config sufficient? Construction-time is simpler and meets the spec; runtime config would add surface area.
- **OQ2**: Does the LLM abstention path need to distinguish "provider unreachable after retries" from "model returned abstention"? Currently `LLMError` is raised for both; a new sub-code (e.g., `llm_retry_exhausted`) could help diagnostics. This is deferred to a follow-up change.
