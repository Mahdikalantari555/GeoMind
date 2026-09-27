## ADDED Requirements

### Requirement: Multipart and JSON client serialization
The web HTTP client SHALL detect `FormData` payloads and omit the `Content-Type` header to allow the browser to supply the correct multipart boundary, while setting `Content-Type: application/json` for non-FormData request bodies.

#### Scenario: Ingest file upload serialization
- **WHEN** the user uploads a file through the Ingest page or dropzone
- **THEN** the request to `POST /api/v1/ingest` is sent with the browser's generated `multipart/form-data; boundary=...` header and accepted by the gateway with `202 Accepted`

### Requirement: End-to-end verified interaction paths and button performance
All interactive buttons, forms, controls, toggles, and functions across all 18 web routes SHALL execute with correct expected performance and semantics:
- Proper pending/loading indicators and disabled states during in-flight network requests.
- Immediate visual and state feedback without dead clicks or silent drops.
- Zero unhandled Promise rejections, blank screens, uncaught exceptions, or unhandled HTTP 4xx/5xx failures.
- Guaranteed toast or inline error/success messaging for all user-initiated actions.

#### Scenario: Button and interactive control functional performance
- **WHEN** any button, tab, modal trigger, dropdown, form submit, or toggle is clicked across any of the 18 web routes
- **THEN** the corresponding handler triggers with appropriate loading/disabled state, dispatches the expected gateway API request or state transition, and updates the UI without regression, UI freezing, or silent failure

#### Scenario: Ingest flow execution
- **WHEN** the user selects a target collection and drops or selects one or multiple supported files (`.md`, `.pdf`, `.txt`, rasters, etc.)
- **THEN** file inputs support multiple selection (`multiple` attribute enabled), an upload job or batch upload jobs are created, the job polling shows progress, and a success or duplicate summary banner is rendered

### Requirement: Automated crawl, telemetry collection, and screenshot verification
The test infrastructure SHALL support automated crawling across all 18 routes in both LTR and RTL modes, capturing console errors, failed network calls, React runtime exceptions, and full-page screenshots for vision model inspection.

#### Scenario: Automated route crawler telemetry
- **WHEN** the automated crawler navigates across all registered application routes
- **THEN** zero uncaught JavaScript runtime exceptions, zero `console.error` calls, and zero unexpected HTTP >= 400 responses are recorded in the crawl report

#### Scenario: Full-page screenshot and visual defect analysis
- **WHEN** the crawler visits each route
- **THEN** full-page screenshots are saved into an audit directory and evaluated for visual defects (text clipping, broken grids, overlapping elements, RTL misalignment, or blank states) before marking the audit phase complete

### Requirement: Single-defect resolution discipline
Bug fixes during the audit SHALL be committed iteratively—one bug category per commit—verifying that each change passes lint, typecheck, unit tests, and automated browser replay before moving to the next defect.

#### Scenario: Defect fix commit isolation
- **WHEN** a console error, network failure, or visual defect is identified
- **THEN** a reproducible test or browser script validates the bug, the targeted fix is applied, all test suites remain green, and the fix is committed before addressing subsequent issues
