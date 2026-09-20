## 1. Provider Settings and Models

- [ ] 1.1 Extend `WorkspaceSettings` with `cloudflare_account_id`,
  `cloudflare_api_token`, and `cloudflare_model_id` fields; verify the model
  accepts these fields and the token is excluded from persistence
- [ ] 1.2 Update the `embedding_provider` literal to include `"cloudflare"`;
  verify `WorkspaceSettings(embedding_provider="cloudflare")` validates

## 2. Cloudflare Provider Implementation

- [ ] 2.1 Add `CloudflareEmbeddingProvider` to
  `embeddings/provider.py` implementing `EmbeddingProvider` with Bearer auth,
  model-specific `space_id`, and L2-normalized float32 output; verify the
  class satisfies the protocol shape
- [ ] 2.2 Implement HTTP POST to the Workers AI `/ai/run/{model_id}` endpoint
  with proper error handling for auth, rate limit, and unknown model failures;
  verify request construction with a mocked transport
- [ ] 2.3 Implement `embed_batch()` chunking using the configured batch size;
  verify batching splits inputs correctly and preserves order

## 3. Factory and Diagnostics

- [ ] 3.1 Extend `build_text_embedder()` to resolve `embedding_provider ==
  "cloudflare"` with a default model and offline refusal; verify the factory
  returns a Cloudflare provider with the expected `model_id` and `space_id`
- [ ] 3.2 Update `doctor_embedding()` to report `active_provider ==
  "cloudflare"` with the resolved model and space id; verify doctor output for
  a cloudflare-configured workspace

## 4. Tests and Documentation

- [ ] 4.1 Add unit tests for provider request auth, batching, error handling,
  and space ids; verify the new test file passes in isolation
- [ ] 4.2 Add a factory resolution test for the cloudflare provider; verify
  the full `libs/geomemory/tests/unit/test_provider.py` (or equivalent) suite
  passes
- [ ] 4.3 Update embedding provider documentation/settings UI copy to mention
  Cloudflare Workers AI; verify the docs render and the settings surface
  exposes the new fields
