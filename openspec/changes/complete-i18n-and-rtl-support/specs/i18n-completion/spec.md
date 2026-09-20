## Purpose

Ensures every user-visible string in the web app comes through the i18next translation system and that both en and fa JSON key trees are complete and in sync, so no English hardcoding leaks into either language direction.

## ADDED Requirements

### Requirement: No hardcoded strings in feature pages
Every user-visible text node rendered by a component under `apps/web/src/features/` SHALL be produced via the `t()` function (or an equivalent i18next hook). Literal English strings directly in JSX SHALL NOT appear as user-facing content.

#### Scenario: Eval page renders translated strings
- **WHEN** a user opens the Evaluation page with language set to fa
- **THEN** the description paragraph, both input placeholders, and the submit button text are rendered in Persian
- **AND** switching back to en renders the same elements in English

#### Scenario: Review page renders translated labels and buttons
- **WHEN** a user opens the Feedback & Review page in fa
- **THEN** status badge labels ("Pending", "Approved", "Rejected"), the state filter options, section headings ("Candidates", "Proposals (diff viewer)"), action buttons ("Promote to Supported", "Promote to Verified", "Reject", "Approve", "Dismiss"), and export-related strings are rendered in Persian
- **AND** switching to en renders all of the above in English

#### Scenario: Overview empty state is translated
- **WHEN** a user views the Overview page with no workspace open in fa
- **THEN** the "No workspace open" heading and the hint paragraph are rendered in Persian

#### Scenario: Agent chat guardrails are translated
- **WHEN** a user opens Agent Chat with no workspace and the error banner renders in fa
- **THEN** "Agent not ready — no workspace open", "Open a workspace to start chatting", and error-action buttons ("Dismiss", "Retry") are rendered in Persian

#### Scenario: Doctor page probes are translated
- **WHEN** a user views the Doctor page during diagnostics in fa
- **THEN** "Loading diagnostics..." and "Probing..." status texts are rendered in Persian

#### Scenario: Ingest page helpers are translated
- **WHEN** a user views the Ingest page with an invalid collection selected in fa
- **THEN** "Select a collection", "Dismiss", and "Retry" helper texts are rendered in Persian

#### Scenario: Ask page metadata labels are translated
- **WHEN** a user views the Ask page in fa
- **THEN** the "model:" metadata label is rendered in Persian

### Requirement: i18n JSON files remain in sync
The `en.json` and `fa.json` files SHALL share an identical key structure under every namespace used by feature pages. A missing key in one file relative to the other SHALL be treated as a defect.

#### Scenario: Key parity check passes
- **WHEN** all namespaces referenced by `apps/web/src/features/` are enumerated from both JSON files
- **THEN** no key exists in one file without a matching key in the other

#### Scenario: Dynamic keys render correctly in both languages
- **WHEN** a template string such as `{{name}}` or `{{count}}` is used in both en and fa entries
- **THEN** interpolation produces correct output in both languages at runtime

## REMOVED Requirements

### Requirement: Partial eval coverage
**Reason**: Replaced by full eval + review + all remaining page coverage requirements above.

## MODIFIED Requirements

### Requirement: Bilingual RTL (from web-app/spec.md)
The UI SHALL support en and fa with runtime switching, `<html dir>` flip, logical-property styling, and Intl formatting. Layout SHALL be smoke-checked in both directions.

#### Scenario: Language switch (existing, unchanged behavior)
- **WHEN** the user switches en → fa
- **THEN** text translates and layout mirrors without broken alignment

#### Scenario: Eval page RTL layout
- **WHEN** the Evaluation page is viewed in fa after all strings are wrapped in `t()`
- **THEN** input fields align to the right, button text is right-aligned, and the gauge icon appears to the left of the button label (mirrored from LTR)

#### Scenario: Review page RTL layout
- **WHEN** the Feedback & Review page is viewed in fa
- **THEN** grid columns, badges, and action buttons render with correct RTL mirroring and no left/right mixing artifacts
