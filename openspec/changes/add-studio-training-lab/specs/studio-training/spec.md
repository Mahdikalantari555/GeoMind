# studio-training

## Purpose

Define the Training Lab: where light models train visibly. Runs are fast
(CPU, seconds), versioned, and reversible. Predictions surface with
calibrated confidence and abstention — never bare labels.

## ADDED Requirements

### Requirement: Train now with live progress
The user SHALL trigger training per key (or all ready keys) as a gateway
background job. The page SHALL render live progress — batch number, samples
consumed, running accuracy — from `job.progress` SSE, with REST catch-up on
reload. The UI SHALL stay interactive during training.

#### Scenario: Run training
- **WHEN** the user clicks "Train now" for a ready key
- **THEN** a job starts, live metrics render, and the UI never blocks

### Requirement: Model versions and rollback
Each trained model SHALL appear in a version list with timestamp, sample
count, and accuracy summary. The last N versions (existing geolearn policy:
10) SHALL support one-click rollback; rollback SHALL be auditable.

#### Scenario: Roll back a bad model
- **WHEN** the user rolls back to a previous version
- **THEN** predictions resume from the previous weights and the rollback is
  recorded

### Requirement: Cold-start transparency
When a key has fewer samples than the classifier threshold (<30), the page
SHALL show the cold-start state explicitly (NN fallback over frozen
embeddings active) and what is needed to graduate to a trained classifier.

#### Scenario: Cold-start key
- **WHEN** a key has 12 samples
- **THEN** the page shows "NN fallback active — 18 more samples to train a
  classifier"

### Requirement: Confidence and abstention surfacing
Prediction displays SHALL always include the confidence score; predictions
below the abstention threshold SHALL render as an explicit abstention — a
bare class label without confidence is forbidden.

#### Scenario: Low-confidence prediction
- **WHEN** a prediction's max probability is below the threshold
- **THEN** the UI renders "abstain (0.42)" instead of a class label
