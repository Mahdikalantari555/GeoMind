# studio-ask

## Purpose

Define the Ask page: grounded Q&A with citation-level provenance and
first-class abstention. Trust is the product: every claim is checkable down
to the segment, and "I don't know" renders as a designed state, not an error.

## ADDED Requirements

### Requirement: Cited answers with claim grounding
Answers SHALL render with per-claim grounding states: fully cited
(citation chips), synthesis-informed, or uncited. Citation chips SHALL open a
split view showing the exact source segment (text locator or raster
metadata) alongside the answer.

#### Scenario: Open a citation
- **WHEN** the user clicks a citation chip
- **THEN** a split view opens with the exact segment highlighted next to
  the answer

#### Scenario: Uncited claim
- **WHEN** an answer contains an uncited claim
- **THEN** that claim is visually marked as uncited, per the grounding
  states

### Requirement: Abstention is first-class
When the backend abstains, the page SHALL render the abstention reason and
the best available retrieval snippets with sources. This state SHALL be
indistinguishable in quality from an answered state (no error styling).

#### Scenario: Abstain without LLM
- **WHEN** no LLM is configured and the user asks a question
- **THEN** retrieval snippets with sources render, with the reason no answer
  was generated and a config affordance

### Requirement: Search mode
The page SHALL provide a pure search mode (no generation) returning ranked
hits with filters (collection, temporal, spatial) and scores.

#### Scenario: Search with filters
- **WHEN** the user searches with a collection filter
- **THEN** only hits from that collection return, ranked with visible scores
