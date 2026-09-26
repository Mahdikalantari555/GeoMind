## Context

Coverage audits across the five core libraries revealed notable gaps:
- `geospatial_core` (81%): `polygonize_array` and complex polygon areas lack coverage.
- `geodomain` (93%): Missing boundary tests for complex temporal intervals.
- `geolearn` (88%): Missing tests for calibration edge paths, adapter shims, and drift fallback modes.
- `geoagent` (75%): `cli.py` has 0% coverage (190 lines), `geolearn_tools.py` has 30% coverage.
- `geomemory` (72%): Large surfaces in `cli/commands/`, `workspace.py`, `lance_backend`, and `pipeline.py` lack coverage.

Reaching >95% across all five requires structured test scaffolding, mock fixtures for external I/O (LLM endpoints, raster files, CLI invocations via `CliRunner`), and synthetic dataset generation.

## Goals / Non-Goals

**Goals:**
- Attain >95% line coverage in `geospatial_core`, `geodomain`, `geolearn`, `geoagent`, and `geomemory`.
- Keep test runtimes fast (target <60s for full core test execution).
- Use hermetic mocks for external services (OpenAI endpoints, HuggingFace downloads).

**Non-Goals:**
- Covering `data_engine` (explicitly excluded due to 8,000+ line legacy surface).
- Adding end-to-end cloud infrastructure tests.

## Decisions

### Decision 1: CLI Testing via Click `CliRunner`
- **Rationale**: `geomemory.cli` and `geoagent.cli` are built with Click. Using `click.testing.CliRunner` allows testing all command groups, option parsing, exit codes, and output formatting in-process without spawning external subshells.

### Decision 2: Mocking Optional Dependencies and Heavy Backends
- **Rationale**: Tests for optional vector backends (e.g. LanceDB or Qdrant) or heavy models (OLMoEarth vision) must use mock or in-memory fixtures so tests remain 100% deterministic and offline.

### Decision 3: Synthetic Raster and Vector Geometries
- **Rationale**: For `geospatial_core` polygonization and area calculations, generate synthetic NumPy grid arrays and shapely GeoJSON geometries with known geometries (cutout donuts, MultiPolygons, 3D vertices) to test edge cases deterministically.

## Risks / Trade-offs

- **[Risk] Test suite execution slowdown** → Mitigation: Use in-memory SQLite (`:memory:`) and small mock arrays (10x10 instead of full satellite scenes) so tests run in milliseconds.
- **[Risk] Flaky tests from network access** → Mitigation: Mock all network calls (`requests`, `urllib`, API clients).
