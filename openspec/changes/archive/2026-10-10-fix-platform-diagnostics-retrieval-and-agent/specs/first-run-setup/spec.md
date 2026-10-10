# Spec Delta: first-run-setup

## ADDED Requirements

### Requirement: Flexible LLM context window limits
Workspace settings and setup validation SHALL accept LLM context windows up to 2,000,000 tokens to support large-context foundation models.

#### Scenario: Configuring a 256k context window
- **WHEN** a user or setup wizard specifies an LLM context window of 256,000 tokens
- **THEN** validation accepts the value without raising a 422 error or out-of-range exception
