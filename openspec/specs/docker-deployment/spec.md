# docker-deployment Specification

## Purpose
Docker images become lightweight and CPU-only via ONNX + sqlite-vec, with measurable size/startup improvement.

## Requirements

### Requirement: Lightweight image (no torch/txtai)
The default `Dockerfile` SHALL build a runnable GeoFoundation stack without `torch` or `txtai` in the image layers; it SHALL include `onnxruntime`, `tokenizers`, `sqlite-vec`, and `huggingface-hub` for the `Xenova/all-MiniLM-L6-v2` quantized model.

#### Scenario: Image size regression gate
- **WHEN** `docker build -t geofoundation:test .` completes
- **THEN** `docker images geofoundation:test --format "{{.Size}}"` is at least 1.5 GB smaller than the last pre-refactor baseline image and `docker run --rm geofoundation:test python -c "import geomemory; print(geomemory.__version__)"` succeeds without importing `torch`

#### Scenario: CPU-only inference
- **WHEN** the container runs `python -c "from geomemory.embeddings.provider import ONNXEmbeddingProvider; print(ONNXEmbeddingProvider().embed(['hello']).shape)"`
- **THEN** it prints `(1, 384)` using `CPUExecutionProvider` without requiring CUDA or `nvidia-smi`

### Requirement: docker-compose has no qdrant service
The `docker-compose.yml` SHALL contain only `gateway` and `web` services
(plus the `workspace_data` volume). No `qdrant` service, no `qdrant_storage`
volume, no qdrant healthcheck.

#### Scenario: compose config is valid
- **WHEN** `docker compose config` is run from the repo root
- **THEN** it exits 0 with only `gateway` and `web` services listed

#### Scenario: Gateway boots without Qdrant
- **WHEN** `docker compose up gateway` completes and the gateway is healthy
- **THEN** `GET http://localhost:8000/health` returns 200 with no qdrant-related errors in the response

### Requirement: Doctor reports qdrant as optional (not absent)
When no qdrant container is reachable, the Doctor SHALL still show the qdrant
diagnostics section with `client_installed` reflecting whether
`qdrant_client` is importable, and `reachable: false` when no URL is
configured.

#### Scenario: Qdrant unreachable but client installed
- **WHEN** `GET /doctor` is called and `qdrant_client` is importable but no qdrant URL is set
- **THEN** `diagnostics.qdrant.client_installed` is `true` and `diagnostics.qdrant.reachable` is `false`
