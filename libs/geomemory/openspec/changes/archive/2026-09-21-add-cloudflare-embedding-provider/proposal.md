# Add Cloudflare Workers AI Text Embedding Provider

## Why

GeoMemory currently supports local ONNX, OpenAI, Voyage, and hashing text
embedding providers, but the cloud provider stubs (`OpenAIEmbeddingProvider`,
`VoyageEmbeddingProvider`, `CustomEmbeddingProvider`) are not implemented,
leaving no working remote embedding option. Adding Cloudflare Workers AI as a
first-class provider gives users a cheap, hosted, API-driven embedding path
without requiring local model downloads, while keeping the existing
`EmbeddingProvider` protocol and space-isolation guarantees intact.

## What Changes

- Add `CloudflareEmbeddingProvider` implementing the existing
  `EmbeddingProvider` protocol, posting batches to the Cloudflare Workers AI
  `/ai/run/{model_id}` endpoint with Bearer-token authentication.
- Extend `WorkspaceSettings.embedding_provider` to accept `"cloudflare"` and
  add the required `cloudflare_account_id` and `cloudflare_api_token` settings
  (token read from env or workspace config, never persisted to the workspace
  database).
- Extend `build_text_embedder()` to resolve the `"cloudflare"` provider,
  defaulting to `@cf/baai/bge-base-en-v1.5` and honoring `offline=True` by
  refusing network-backed embedding.
- Emit a dedicated `space_id` (`text.cloudflare.<model>.v1`) so indexes built
  with Cloudflare embeddings cannot be mixed with ONNX or other provider
  spaces.
- Add unit tests for provider request construction, batching, error handling,
  and factory resolution; update doctor diagnostics to report the active
  provider.

## Capabilities

### New Capabilities
- `cloudflare-embedding-provider`: text embeddings via Cloudflare Workers AI
  with API-key authentication, model selection, batching, offline refusal, and
  isolated `text.cloudflare.*` space ids.

### Modified Capabilities
- (none)

## Impact

- `libs/geomemory/src/geomemory/embeddings/provider.py` — new provider class
- `libs/geomemory/src/geomemory/embeddings/factory.py` — cloudflare dispatch
- `libs/geomemory/src/geomemory/core/models.py` — settings fields
- `libs/geomemory/src/geomemory/services/doctor.py` (or equivalent diagnostics
  surface) — active provider reporting
- `libs/geomemory/tests/` — new unit tests for the provider and factory
