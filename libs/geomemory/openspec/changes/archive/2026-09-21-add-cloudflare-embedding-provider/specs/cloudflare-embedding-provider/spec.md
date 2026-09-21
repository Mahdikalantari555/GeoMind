# Cloudflare Workers AI Text Embedding Provider Specification

## Purpose

Provides a hosted, API-driven text embedding provider via Cloudflare Workers AI
so users can embed text without downloading or running local models, while
preserving the existing `EmbeddingProvider` contract and space isolation.

## ADDED Requirements

### Requirement: Cloudflare provider authenticates with Workers AI API
The system SHALL authenticate to Cloudflare Workers AI using an API token and
account ID, sending the token as a Bearer credential on every embedding
request. The token SHALL be configurable via `cloudflare_api_token` and
`cloudflare_account_id` settings, and SHALL be read from environment variables
or workspace configuration without being persisted to the workspace database.

#### Scenario: Token sent as Bearer credential
- **WHEN** an embedding request is made with a configured Cloudflare token
- **THEN** the request includes `Authorization: Bearer <token>`

#### Scenario: Token not persisted
- **WHEN** a workspace is saved after configuring the Cloudflare provider
- **THEN** the API token is not written to `workspace.yaml`

### Requirement: Cloudflare provider embeds text via Workers AI
The system SHALL embed text by POSTing batches to the Cloudflare Workers AI
`/ai/run/{model_id}` endpoint for the configured model, and SHALL return
L2-normalized float32 vectors with the same dimension as the selected model.

#### Scenario: Successful embedding
- **WHEN** `embed()` is called with a list of texts and the Workers AI endpoint
  returns vectors
- **THEN** the provider returns an `(N, D)` float32 array, one vector per text,
  L2-normalized

#### Scenario: Batch embedding
- **WHEN** `embed_batch()` is called with a batch size smaller than the input
- **THEN** texts are split into chunks of at most `batch_size` and each chunk is
  posted as a separate request

### Requirement: Cloudflare provider uses isolated space ids
The provider SHALL emit a `space_id` of the form `text.cloudflare.<model>.v1`
that is distinct from ONNX, OpenAI, Voyage, and hashing spaces, so indexes
built with Cloudflare embeddings are never mixed with other providers.

#### Scenario: Unique space id
- **WHEN** a Cloudflare provider is created for `@cf/baai/bge-base-en-v1.5`
- **THEN** `space_id` equals `text.cloudflare.cf-baai-bge-base-en-v1-5.v1`

### Requirement: Cloudflare provider refuses to embed when offline
The provider SHALL refuse network-backed embedding when `offline=True` is set,
raising a clear error instead of silently falling back to a local model or
degrading silently.

#### Scenario: Offline refusal
- **WHEN** `embed()` is called with `offline=True` and no local cache is
  available
- **THEN** an `EmbeddingUnavailableError` (or equivalent) is raised with a
  message indicating that Cloudflare requires network access

### Requirement: Cloudflare provider is selectable in workspace settings
The system SHALL accept `embedding_provider="cloudflare"` in workspace
settings, defaulting to model `@cf/baai/bge-base-en-v1.5` when no explicit
model is configured, and the factory SHALL return a Cloudflare provider for
this selection.

#### Scenario: Factory resolves cloudflare
- **WHEN** `build_text_embedder()` is called with
  `embedding_provider="cloudflare"`
- **THEN** it returns a provider whose `model_id` is the configured Cloudflare
  model and whose `space_id` uses the `text.cloudflare.*` prefix

### Requirement: Doctor reports Cloudflare as active provider
The doctor diagnostics SHALL report `embedding_provider` as `cloudflare` when
that provider is active, and SHALL include the resolved model and space id in
its response.

#### Scenario: Doctor shows cloudflare
- **WHEN** `doctor_embedding()` is called with
  `embedding_provider="cloudflare"`
- **THEN** the response contains `active_provider == "cloudflare"` and the
  corresponding `active_model` and `active_space_id`
