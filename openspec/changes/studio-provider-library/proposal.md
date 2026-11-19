# Discover chat models from Studio

Settings previously edited React state; `/models` scans the local embedding hub, not a remote chat catalog. Keep these workflows separate. A named provider binds one server-approved base URL to its own environment key. Studio loads the catalog, discovers IDs, and remembers checked IDs in this browser by endpoint. Applying one selected ID uses the existing workspace settings transaction; an agent using old settings must be reinitialized. A check adds a shortcut, not a download, inference or billing event.

Gateway: GET `/api/v1/providers`; GET `/api/v1/providers/{name}/models`; existing PUT `/api/v1/workspace/settings`. Discovery requires an open, online-enabled workspace. Default catalog: OpenAI and OpenRouter; a custom base is configured by the operator. Do not forward a shared credential to arbitrary browser-supplied destinations or follow redirects. Model listing is not proof that the key has inference permission or that the model supports chat. No automatic real inference test.

Acceptance: check two IDs, apply exactly one, reload, re-open provider and see both saved; offline/unknown destinations never contacted; empty result distinguished from failure. Scope: single-box trusted-local gateway, not multi-user secret management. Deployment with multiple users needs authorization and per-user credential isolation first. QA status and follow-ups: `docs/qa/studio-audit.md`.

Follow-up: Studio now offers an exact-URL connection wizard (`POST /api/v1/providers/connect`) for HTTPS bases in `GEOMIND_APPROVED_PROVIDER_BASES`. Each has a distinct credential slot; changing the URL never carries credentials forward. The model list supports filtering independently of the library selection.
