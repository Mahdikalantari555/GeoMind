# Design: Cloudflare Workers AI Text Embedding Provider

## Context

See proposal.md - Why. The current `EmbeddingProvider` protocol is already
provider-agnostic, and `build_text_embedder()` dispatches on
`embedding_provider`. Cloudflare Workers AI is a natural fit: it exposes
embedding models over a simple HTTPS API, has a generous free tier, and does
not require local model downloads. The main design constraint is that remote
embeddings must never be mixed with local ONNX or other provider spaces.

## Goals / Non-Goals

**Goals:**
- Add a working, authenticated Cloudflare Workers AI text embedding provider
- Keep the existing `EmbeddingProvider` protocol and factory-based selection
- Preserve space isolation with a dedicated `text.cloudflare.*` prefix
- Support batching and offline refusal
- Report the active provider in doctor diagnostics

**Non-Goals:**
- Vision embeddings via Cloudflare (keep OLMoEarth local)
- Replacing the default ONNX provider or changing existing indexes
- Streaming or incremental embedding
- Implementing the other cloud stubs (OpenAI, Voyage, Custom)

## Decisions

### Decision 1: Use Cloudflare Workers AI REST API directly
The provider posts to
`https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_id}`
with a Bearer token. This avoids adding a new SDK dependency and keeps the
runtime footprint small.

- Alternatives considered: Cloudflare Python SDK (extra dependency, more
  surface area), Workers AI via a proxy endpoint (adds infrastructure)
- Rationale: Direct REST is the smallest, most transparent integration

### Decision 2: Add provider-specific settings fields
Add `cloudflare_account_id` and `cloudflare_api_token` to `WorkspaceSettings`,
following the same pattern as `llm_api_key_env` and `qdrant_api_key`. The
token is read at call time and never persisted.

- Alternatives considered: Reusing `llm_api_key` (wrong domain, conflates LLM
  and embedding credentials), single `cloudflare_api_token` only (account ID
  is required by the endpoint)
- Rationale: Explicit fields keep secrets scoped to their provider

### Decision 3: Default to `@cf/baai/bge-base-en-v1.5`
This is a well-supported, English BGE model on Workers AI with good quality
and a 768-d output. The model id is configurable via
`cloudflare_model_id` (or a dedicated `onnx_model_name`-like field).

- Alternatives considered: `@cf/baai/bge-small-en-v1.5` (smaller, lower
  quality), `@cf/baai/bge-large-en-v1.5` (higher quality, more latency)
- Rationale: Base is the best default balance for a general-purpose
  embedding provider

### Decision 4: Use `text.cloudflare.<model>.v1` for space ids
The space id is derived from the model id with the same safe-name
normalization used by ONNX (`/` → `-`, `.` → `-`), prefixed with
`text.cloudflare.`.

- Alternatives considered: Reusing `text.onnx.*` (would corrupt index
  isolation), a fixed `text.cloudflare.v1` (collides across models)
- Rationale: Keeps the existing space-id convention while guaranteeing
  isolation per model

### Decision 5: Batch via `embed_batch()` with configurable batch size
Use the workspace `batch_size` setting (default 64) to chunk texts before
posting, matching the existing provider interface.

- Alternatives considered: One request per text (high latency), fixed batch
  size of 1 (no batching benefit)
- Rationale: Reuses the existing interface and lets users tune cost/latency

## Risks / Trade-offs

- **[Network dependency]** Cloudflare requires internet access; mitigated by
  `offline=True` refusal and clear error messages
- **[Embedding space mismatch]** Cloudflare vectors differ from ONNX vectors;
  mitigated by the dedicated `text.cloudflare.*` space id and reindex
  requirement
- **[API rate limits / cost]** Workers AI has per-account limits; mitigated by
  batching and documentation
- **[Token exposure]** API token must not be persisted; mitigated by reading
  from env/config at call time only
- **[Model availability]** Cloudflare model ids can change; mitigated by
  making the model configurable and failing clearly on unknown ids

## Migration Plan

1. Add the provider class, settings fields, factory dispatch, and doctor
   reporting
2. Add unit tests for request construction, batching, offline refusal, and
   factory resolution
3. Document the new provider in the settings UI/docs
4. Users with existing ONNX indexes do not need to reindex unless they switch
   providers; switching to Cloudflare requires a fresh index under the new
   space id

## Open Questions

- Should `cloudflare_model_id` live on `WorkspaceSettings` or reuse
  `onnx_model_name`? (Proposal assumes a dedicated field for clarity.)
- Should the provider support a configurable Workers AI base URL for
  self-hosted or regional deployments? (Can be added later without changing
  the spec.)
