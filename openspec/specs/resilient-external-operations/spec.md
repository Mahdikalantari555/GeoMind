# resilient-external-operations Specification

## Purpose
Define observable retry, backoff, and timeout behavior for all external network calls (LLM provider, Open-Meteo weather, Planetary Computer STAC) and the SQLite connection policy, so that transient failures do not surface as hard errors to callers or the active workspace.

## Requirements

### Requirement: LLM chat retries on 429 and 503
`OpenAICompatBackend.chat()` SHALL retry on HTTP 429 (Too Many Requests) and 503 (Service Unavailable) responses from the upstream LLM provider. The backend SHALL use exponential backoff with a configurable `max_attempts` (default 3) and an initial delay (default 1 s). After exhausting all attempts the backend SHALL raise `LLMError` carrying the last response status code and body so the caller can distinguish retry exhaustion from first-attempt errors. Connections refused (URLError) SHALL also be retried up to `max_attempts`.

#### Scenario: Retry on 429
- **WHEN** the LLM provider returns HTTP 429 on the first call
- **THEN** the backend waits the configured backoff interval and retries (up to `max_attempts`)
- **AND** a successful subsequent response returns normally to the caller

#### Scenario: Retry exhaustion surfaces error
- **WHEN** all retry attempts return 429 or 503
- **THEN** `LLMError` is raised with a message containing the final HTTP status code
- **AND** no cached or partial response is returned to the caller

#### Scenario: Non-retryable errors are not retried
- **WHEN** the LLM provider returns a non-retryable status such as 400 or 401
- **THEN** the backend raises `LLMError` immediately without retry

#### Scenario: URLError is retried
- **WHEN** `urllib.error.URLError` is raised (connection refused, DNS failure)
- **THEN** the backend retries up to `max_attempts` with exponential backoff before raising

### Requirement: Weather API retries on transient errors
`DynamicWeatherFetcher` SHALL retry failed requests to Open-Meteo on HTTP 429, 502, 503, and 504, and on network-level exceptions. The retry policy SHALL use exponential backoff with `max_attempts=3` and an initial delay of 1 s. On exhaustion the method SHALL return `None` and log a warning (preserving the existing error-silencing contract). The overall request timeout SHALL remain respected per attempt.

#### Scenario: Retry on Open-Meteo 429
- **WHEN** Open-Meteo returns HTTP 429 during a weather fetch
- **THEN** the method retries after exponential backoff and returns valid data on success
- **AND** no exception propagates to the caller

#### Scenario: Exhausted retries return None
- **WHEN** all retry attempts fail
- **THEN** the method returns `None`
- **AND** a warning is logged with the final error

### Requirement: STAC search/download retries
`PlanetaryComputerFetcher.search_scenes()` and its download methods SHALL retry transient failures — HTTP 429, 502, 503, 504, and `requests.RequestException` — using exponential backoff with `max_attempts=3` and initial delay of 1 s. Retry failures SHALL propagate the final error (not silently swallowed) so that pipeline stages can detect scene-listing failures.

#### Scenario: STAC search retry on 429
- **WHEN** the STAC catalog returns HTTP 429 during search
- **THEN** the fetcher retries after exponential backoff and returns results on success
- **AND** a successful response contains the same items structure as without retries

#### Scenario: STAC download retry on 503
- **WHEN** a scene asset download returns HTTP 503
- **THEN** the download attempt retries with backoff before raising

#### Scenario: Non-transient errors are not retried
- **WHEN** the STAC service returns 404 for a missing collection
- **THEN** the error is raised immediately without retry

### Requirement: SQLite busy_timeout raised to 30 s
The SQLite connection pragma `busy_timeout` SHALL be set to 30 000 ms (30 s) instead of the current 5 000 ms. This reduces `sqlite3.OperationalError: database is locked` exceptions during concurrent reads under the single-writer server model. The change SHALL apply to every new connection established by `geomemory.storage.database.connect()`.

#### Scenario: Connection uses 30 s busy_timeout
- **WHEN** a new database connection is opened via `connect()`
- **THEN** `PRAGMA busy_timeout` reports `30000`
- **AND** concurrent read attempts within 30 s of a write wait rather than raising `SQLITE_BUSY`

#### Scenario: Existing WAL mode preserved
- **WHEN** the connection is opened
- **THEN** `PRAGMA journal_mode` remains `WAL`
- **AND** `PRAGMA foreign_keys` remains `ON`

### Requirement: Tool registry daemon-thread cleanup
`ToolRegistry.execute()` SHALL ensure that when a tool times out, the worker thread is not left as a dangling orphan. The method SHALL join with a finite timeout, cancel logical processing via the result object, and allow garbage collection. No new unbounded thread accumulation SHALL occur after repeated timeout invocations.

#### Scenario: Timed-out tool does not leak threads
- **WHEN** a tool exceeds its configured timeout
- **THEN** `Thread.is_alive()` is `False` after `execute()` returns
- **AND** `ToolResult(status="timeout", ...)` is returned to the caller

#### Scenario: Repeated timeouts preserve health
- **WHEN** multiple tools time out in succession
- **THEN** the number of alive daemon threads in the process does not grow monotonically
- **AND** no `ResourceWarning` about unclosed threads is emitted
