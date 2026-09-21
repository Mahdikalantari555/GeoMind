## Purpose

Define the end-to-end guarantee that every Citation in a QAResult carries a valid, non-empty answer_id linking it back to its parent Answer.

## ADDED Requirements

### Requirement: Citation answer_id SHALL be populated
Every `Citation` object created by `ChatService.ask()` SHALL have a non-empty `answer_id` field that matches the ID of the persisted `Answer` row in the database.

#### Scenario: map_citations receives real answer_id
- **WHEN** `ChatService.ask()` persists an answer and then maps citations
- **THEN** `map_citations()` SHALL receive the actual answer row ID (not empty string)
- **AND** each resulting `Citation.answer_id` SHALL equal that ID

#### Scenario: QAResult citations are traceable
- **WHEN** a client receives a `QAResult` from `POST /api/v1/ask`
- **THEN** every `citation.answer_id` in the response SHALL be a non-empty UUID string
- **AND** that answer_id SHALL correspond to a row in the `answer` table

#### Scenario: _persist_answer remains correct after fix
- **WHEN** `_persist_answer()` is called after the chat_service fix
- **THEN** it SHALL still insert citations correctly (may become a no-op duplicate write for answer_id, which is acceptable)
- **AND** the final database state SHALL have correct foreign-key relationships

### Requirement: Regression test for citation provenance
A new test SHALL assert that `QAResult.citations[i].answer_id` is non-empty and matches the persisted answer ID.

#### Scenario: Test passes with mocked LLM
- **WHEN** the test runs `GeoMemory.ask()` with a mocked LLM backend that returns a citation-rich answer
- **THEN** `result.citations` SHALL be non-empty
- **AND** `result.citations[0].answer_id` SHALL be a non-empty string equal to the persisted answer ID

### Requirement: chat_service answer persistence order
`ChatService.ask()` SHALL persist the answer to the database BEFORE calling `map_citations()`, so that the generated answer ID is available for citation linkage.

#### Scenario: Correct call ordering
- **WHEN** `chat_service.py` executes the ask flow
- **THEN** `self.conn.execute("INSERT INTO answer ...")` SHALL happen before `map_citations(answer_id, ...)`
- **AND** `self.conn.commit()` SHALL happen after both the answer insert and citation inserts
