## Purpose

Define the type-safety requirements for all libraries in the GeoFoundation monorepo.

## ADDED Requirements

### Requirement: All libraries SHALL declare py.typed
Every library package (`geomemory`, `geoagent`, `geolearn`, `data_engine`) SHALL include an empty `py.typed` marker file at the package root (e.g., `src/geomemory/py.typed`). This enables mypy to perform strict type checking across library boundaries.

#### Scenario: Server mypy sees geoagent types
- **WHEN** `mypy --strict` runs on `server/src/`
- **THEN** imports like `from geoagent.agent import AgentCore` SHALL be fully type-checked (not skipped as untyped)
- **AND** no `import-untyped` errors SHALL remain for internal lib imports

#### Scenario: Cross-library type checking
- **WHEN** `mypy --strict` runs on `server/src/geofront_api/services/agent.py`
- **THEN** all type annotations from `geoagent.*` imports SHALL be resolved
- **AND** the 11 previously-suppressed `import-untyped` errors SHALL be eliminated

### Requirement: geomemory SHALL pass mypy --strict
After this change, `mypy --strict libs/geomemory/src/` SHALL report zero errors.

#### Scenario: no-any-return elimination
- **WHEN** mypy analyzes `api_backend.py`, `sqlite_vec_backend.py`, `index_service.py`
- **THEN** all `Any` returns SHALL be replaced with properly typed returns or explicit `reveal_type` suppression with justification

#### Scenario: Literal vs str alignment
- **WHEN** mypy analyzes `workspace.py`, `pipeline.py`, `entity_repo.py`
- **THEN** `Literal['document', 'code', 'raster', 'vector', 'table']` SHALL be used where validators enforce those values
- **AND** `arg-type` errors SHALL be eliminated

#### Scenario: Protocol compliance
- **WHEN** mypy analyzes `index_service.py` calls to `SqliteVecBackend.load()` and `VectorBackend.load()`
- **THEN** signatures SHALL match the `StorageBackend` protocol
- **AND** `protocol-assignment` errors SHALL be eliminated

### Requirement: data_engine SHALL have no runtime-breaking type errors
After this change, all references to non-existent classes (`PipelineSettings`, `process_scene`, `AnchorPixelManager`) SHALL be fixed to reference the actual class names.

#### Scenario: CLI references correct classes
- **WHEN** `libs/data_engine/src/data_engine/cli/interface.py` is type-checked
- **THEN** all class references SHALL resolve to existing definitions
- **AND** the 780 mypy errors SHALL be reduced to zero (or to pre-existing known suppressions with justification)

### Requirement: server mypy configuration
The server's `pyproject.toml` mypy config SHALL remove `disable_error_code = ["import-untyped"]` once all libs declare `py.typed`, enabling full strict checking across the boundary.

#### Scenario: Full strict checking enabled
- **WHEN** all four libs have `py.typed`
- **THEN** `server/pyproject.toml` SHALL remove the `import-untyped` suppression
- **AND** `mypy --strict server/src/` SHALL report zero errors
