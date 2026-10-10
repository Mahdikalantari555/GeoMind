# Spec Delta: retrieval-parity

## Purpose

Ensures consistent vector and keyword retrieval behavior across embedding providers, language scripts, and document segmentation boundaries.

## ADDED Requirements

### Requirement: Dynamic space ID resolution for dense search
The system SHALL resolve the active vector space ID from current workspace settings (active embedding provider and model) rather than a hardcoded string.

#### Scenario: Dense search uses configured space
- **WHEN** dense search runs in a workspace configured with an ONNX or hashing embedding provider
- **THEN** the system queries the vector table matching the active space ID and does not fall back to character n-gram search when the table exists

### Requirement: Multilingual and RTL keyword extraction
The system SHALL preserve non-ASCII Unicode tokens in full-text search term extraction, and SHALL execute dense-only retrieval when a query contains no ASCII alphanumeric terms.

#### Scenario: Persian query execution
- **WHEN** a user searches with Persian query text such as "تنش"
- **THEN** the system does not drop all query terms and executes retrieval without returning an immediate empty result

### Requirement: Accurate page locators and header heuristics for document chunks
The document ingestion chunkers SHALL calculate segment locators using accurate document page numbers based on source page offsets, and SHALL NOT misclassify uppercase abbreviations or formulas as section headers.

#### Scenario: Multi-page document citations
- **WHEN** a multi-page document is ingested and chunked
- **THEN** chunks from page 2 and later receive locators reflecting their true page number rather than defaulting to page 0

#### Scenario: Uppercase acronyms preserved without fragmentation
- **WHEN** document text contains uppercase strings such as acronyms or hash identifiers
- **THEN** the chunker does not create an isolated section break unless preceded and followed by paragraph breaks

### Requirement: Reliable model classification and weight validation in hub
`EmbeddingModelHub` SHALL exclude vision models from text embedder listings and SHALL verify the presence of model weights files (e.g. `pytorch_model.bin`, `model.safetensors`, `model.onnx`) before classifying a directory as downloaded and loadable.

#### Scenario: Vision model scan
- **WHEN** `EmbeddingModelHub.scan()` encounters vision model checkpoints such as OlmoEarth
- **THEN** the model is not classified as a sentence-transformers text embedder

#### Scenario: Tokenizer-only directory
- **WHEN** a model directory contains only configuration and tokenizer files without weight artifacts
- **THEN** the hub reports the model as not downloaded / not loadable, allowing download of actual weights
