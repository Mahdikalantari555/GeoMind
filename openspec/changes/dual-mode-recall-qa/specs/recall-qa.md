# Specification: Dual-Mode Recall & Grounded QA

## Requirements

### Requirement 1: Unified Search & QA Split View (`uBfSK.jpg`)
The system MUST provide a split view displaying ranked search hits on the left and grounded QA on the right.

#### Scenario: Submitting a query
- **Given** an open workspace with indexed documents
- **When** the user submits a search query in the unified interface
- **Then** the left pane displays matching segments with similarity percentages and polygon previews
- **And** the right pane displays the QA response card with confidence badge and citation drawer.

### Requirement 2: Fast Recall vs Slow Synthesis
The QA engine MUST support fast extractive recall without requiring an LLM backend.

#### Scenario: Running fast recall
- **Given** no LLM provider or API key is configured
- **When** the user selects "Fast Recall" mode and asks a question
- **Then** the system returns matching text segments and citation objects with `model: "recall"`
- **And** the latency is under 150ms.

### Requirement 3: Sentence-Level Citation & Provenance Drawer
The interface MUST support inline citation chips that reveal the full provenance chain.

#### Scenario: Inspecting a citation
- **Given** an answer with citation chips `[1]`
- **When** the user clicks citation chip `[1]`
- **Then** a provenance drawer slides open showing segment text, locator metadata, and asset SHA-256.

### Requirement 4: Structured Abstention State
The system MUST render a structured abstention panel when retrieved context is insufficient.

#### Scenario: Querying out-of-scope topics
- **Given** a query with no matches above the retrieval threshold
- **When** the answer returns with `abstained: true`
- **Then** the UI displays an amber diagnostic banner explaining the abstention reason with a direct link to the Ingest page.
