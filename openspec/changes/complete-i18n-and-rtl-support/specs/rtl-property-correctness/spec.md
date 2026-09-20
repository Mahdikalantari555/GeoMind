## Purpose

Guarantees that all Tailwind spacing/layout classes used in feature-page components are logical-properties-compliant so layout flips correctly when the document direction is RTL.

## ADDED Requirements

### Requirement: No physical directional spacing in feature pages
Component JSX under `apps/web/src/features/` SHALL NOT use physical directional Tailwind utilities (`ml-*`, `mr-*`, `pl-*`, `pr-*`, `left-*`, `right-*`, `float-left`, `float-right`). Logical equivalents (`ms-*`, `me-*`, `ps-*`, `pe-*`) SHALL be used instead.

#### Scenario: Search hit modality chip uses logical margin
- **WHEN** a search result modality chip renders in fa
- **THEN** the chip's start-margin class is `ms-1.5` (not `ml-1.5`) so it appears to the left of the title in LTR and to the right in RTL

#### Scenario: No physical margins survive lint or audit
- **WHEN** a full scan of `apps/web/src/features/**/*.tsx` is run for physical spacing classes
- **THEN** zero matches for `ml-`, `mr-`, `pl-`, `pr-`, `float-left`, `float-right` are reported

### Requirement: Logical properties preserved across language switch
Layout spacing SHALL remain visually correct after switching between en and fa.

#### Scenario: Spacing parity after language toggle
- **WHEN** the user toggles between en and fa on any feature page
- **THEN** spacing between elements (margins, padding) preserves visual intent without flipping or misalignment

## MODIFIED Requirements

### Requirement: Full feature coverage (from web-app/spec.md)
The app SHALL provide pages for ... eval benchmarks ... — with the added constraint that all text in those pages is i18n-wrapped (see i18n-completion spec) and all layout uses logical properties (this spec).

#### Scenario: E2E smoke checks RTL layout on all pages
- **WHEN** the Playwright E2E suite runs RTL smoke tests on every feature page after this change
- **THEN** no physical directional class remains and no layout misalignment is detected in fa mode
