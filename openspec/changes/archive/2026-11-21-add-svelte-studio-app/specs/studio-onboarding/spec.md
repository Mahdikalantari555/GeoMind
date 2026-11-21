# studio-onboarding

## Purpose

Define the first-run experience. The old app had no guided path — a new user
could not reach a first cited answer. This capability makes "cited answer in
under 2 minutes" the measurable onboarding contract.

## ADDED Requirements

### Requirement: One-button sample workspace
On first launch with no workspace, the app SHALL show a single primary
action: "Try sample workspace". Clicking it SHALL seed a bundled demo
workspace (sample raster scene, farms GeoJSON, sample PDFs — pre-indexed
assets) and open the map. The alternative path (open/create a real
workspace) SHALL remain visible as a secondary action.

#### Scenario: First launch
- **WHEN** the app launches with no existing workspace
- **THEN** the primary action is "Try sample workspace" with a visible
  secondary "open a real workspace" path

#### Scenario: Sample seeded
- **WHEN** the user clicks the sample action
- **THEN** the demo workspace is created, seeded, opened, and the map shows
  the sample scene without further clicks

### Requirement: First answer in under two minutes
From first launch to a first cited answer SHALL take under two minutes of
user actions, with no configuration required before the first answer. The
seeded flow SHALL guide: sample workspace → ask a sample question → cited
answer with citation chips.

#### Scenario: Guided first question
- **WHEN** the sample workspace opens
- **THEN** the UI offers one sample question; answering it returns a cited
  answer or an abstention with sources

### Requirement: LLM configuration deferred
LLM configuration SHALL be requested only after the first answer is shown.
Before that, the app SHALL operate in retrieval-only mode (search results
with sources work with no LLM).

#### Scenario: Config after first answer
- **WHEN** the first answer is displayed without an LLM configured
- **THEN** a non-blocking affordance offers LLM setup, dismissible without
  losing the answer
