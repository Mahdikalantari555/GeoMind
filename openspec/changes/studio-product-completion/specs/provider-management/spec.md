# provider-management — Spec Delta

## ADDED Requirements

### Requirement: Register a custom provider

An admin SHALL register an OpenAI-compatible provider by supplying a name, an
HTTPS base URL (HTTP only for loopback) and a key-env slot. The provider SHALL
appear in `GET /providers` and be selectable in Studio. A URL with credentials,
query or fragment SHALL be rejected; changing the URL SHALL assign a fresh key
slot so credentials never carry over.

#### Scenario: admin registers a provider
- **WHEN** an admin POSTs `{name: "Lab LLM", base: "https://llm.lab/v1"}`
- **THEN** `GET /providers` lists it with its derived key-env name

#### Scenario: arbitrary destination is rejected
- **WHEN** a non-admin POSTs a provider with an arbitrary base URL
- **THEN** 403/422 is returned and nothing is registered

### Requirement: Runtime API key entry

A user SHALL submit `llm_api_key` at runtime in `PUT /workspace/settings`. It
SHALL be written only to the process environment named by `llm_api_key_env` —
never to the workspace DB or returned in any response. `llm_api_key_env` SHALL
accept built-in or registered-provider names only; `PATH` SHALL be rejected.

#### Scenario: key is accepted but never echoed
- **WHEN** `llm_api_key` is set and settings are read back
- **THEN** a configured flag is true, no value is returned, no key is on disk
