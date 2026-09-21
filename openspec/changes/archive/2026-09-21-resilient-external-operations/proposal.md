## Why

External operations across GeoFoundation — LLM API calls, weather data fetching, and STAC asset downloads — lack any retry logic, causing transient failures (429 rate-limit, 503 unavailable, network blips) to surface as hard errors that abort workspaces, ETa computations, or scene lookups. Additionally, a daemon-thread leak on tool timeout and an undersized SQLite busy_timeout compound fragility under load. This change introduces structured resilience so the platform degrades gracefully instead of crashing on recoverable errors.

## What Changes

- Add retry-and-backoff middleware to `OpenAICompatBackend.chat()` covering HTTP 429 and 503 with configurable max attempts and delay
- Add retry-and-backoff around `requests.get` in `DynamicWeatherFetcher` for transient Open-Meteo errors
- Add retry-and-backoff around STAC client search/download calls in `PlanetaryComputerFetcher`
- Fix the daemon thread leak in `ToolRegistry.execute()`: set a proper timeout reference and join cleanly instead of leaving timed-out threads dangling
- Raise SQLite `busy_timeout` from 5000 ms to 30000 ms to reduce transient `SQLITE_BUSY` errors under concurrent reads
- Add `tenacity` as a shared dependency to `libs/geoagent` and `libs/data_engine` (it is not yet present in any pyproject.toml)

## Capabilities

### New Capabilities
- `resilient-external-operations`: Defines retry behavior, backoff strategy, and failure-handling contracts for all external network calls (LLM, weather, STAC) and the SQLite connection policy.

### Modified Capabilities
<!-- None yet — if existing spec requirements change, they would be listed here -->

## Impact

- **libs/geoagent** (`src/geoagent/llm/openai_compat.py`, `src/geoagent/registry.py`): Adds tenacity retries to LLM chat calls; cleans up daemon-thread timeout handling in the tool registry.
- **libs/data_engine** (`src/data_engine/io/dynamic_weather_fetcher.py`, `src/data_engine/io/planetary_computer_fetcher.py`): Wraps HTTP requests and STAC searches in tenacity retry decorators.
- **libs/geomemory** (`src/geomemory/storage/database.py`): Raises `busy_timeout` pragma constant.
- **server**: No behavioral change expected, but may surface fewer transient 503s during integration tests.
- **New dependency**: `tenacity>=8.0` added to `libs/geoagent/pyproject.toml` and `libs/data_engine/pyproject.toml`.
- **Breaking**: No API-level breaking changes. Internal module imports of tenacity are implementation-only.
