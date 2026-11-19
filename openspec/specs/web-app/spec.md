# web-app Specification

## Purpose
TBD - created by archiving change add-web-app. Update Purpose after archive.

## Requirements

### Requirement: Full feature coverage
The app SHALL provide pages for workspace lifecycle/stats/settings/doctor,
collections, ingest (with dedup banner), search (modes + spatial/temporal/
sensor filters + bbox draw), grounded ask (citations + abstention), assets
inspect, index management, feedback review/export, eval benchmarks, agent
chat (SSE, tool-run timeline, guardrail cards), conversations, tools
catalog, playbooks, maps viewer, and farms reports.

#### Scenario: Search with all filters
- **WHEN** a user sets mode=hybrid, draws a bbox, picks a date range and
  sensor chips, and runs a query
- **THEN** results render with score breakdown and locator chips

### Requirement: Bilingual RTL
The UI SHALL support en and fa with runtime switching, `<html dir>` flip,
logical-property styling, and Intl formatting. Layout SHALL be smoke-checked
in both directions.

#### Scenario: Language switch
- **WHEN** the user switches en → fa
- **THEN** text translates and layout mirrors without broken alignment

### Requirement: Gateway-only consumption
The app SHALL call only the gateway `/api/v1` (generated client) and SHALL
NOT import or assume direct library access.

#### Scenario: Client generation
- **WHEN** the OpenAPI schema changes and the client is regenerated
- **THEN** type errors surface at build time, not runtime

### Requirement: Realtime updates
Workspace/asset/collection stats SHALL refresh via SSE invalidation without
manual reload; long jobs SHALL show progress.

#### Scenario: Ingest completes while viewing Overview
- **WHEN** an ingest job finishes and `asset_created` arrives
- **THEN** stats cards and asset lists update automatically

### Requirement: Graceful degradation
Gateway down, workspace closed, and LLM-unavailable SHALL render explicit
status states (connection pill, abstention cards with reason), never blank
screens or crashes.

#### Scenario: LLM key missing
- **WHEN** the user opens Ask with no API key configured
- **THEN** the answer renders as an abstention card with the reason

### Requirement: No silent failures — global error surfacing
The app SHALL surface every 4xx/5xx, network failure, SSE disconnect, and job failure as a visible banner/toast with `code` + `message` + retry action, never as a blank screen or console-only error.

#### Scenario: Global boundary
- **WHEN** any page throws or any `openapi-fetch` call returns non-2xx
- **THEN** an `ErrorBoundary` / query `onError` renders an alert banner with the envelope's `code` and `message` and a retry button that reissues the request

#### Scenario: SSE disconnect
- **WHEN** the `GET /api/v1/events` or `POST /api/v1/agent/chat` stream disconnects or emits `error`
- **THEN** the UI shows a reconnecting/error banner (not silent disappearance) and offers retry

### Requirement: Ingest page explicit states
The Ingest page SHALL show queued→running→done/error per job, dedup (`skipped:true`) banner, collection-missing and workspace-closed guards, and field-level validation (unsupported format, 413) with the accepted types list.

#### Scenario: Duplicate upload
- **WHEN** a file with previously ingested SHA-256 is uploaded
- **THEN** a dedup banner appears ("Already ingested — skipped") and `segment_count` is not incremented

#### Scenario: Upload without collection
- **WHEN** user attempts upload with no collection selected
- **THEN** the submit button is disabled and a helper text "Select a collection" is shown; if bypassed, server 422 is rendered as a banner

### Requirement: Agent chat explicit states
Agent Chat SHALL stream `thinking` → tool timeline → messages with citation chips, and on `error`/`guardrail`/`abstention` SHALL render a card with `code/reason` and a retry/abort control; aborted streams SHALL show "Cancelled" not silent.

#### Scenario: Chat without workspace
- **WHEN** the user opens Chat with no workspace open
- **THEN** a `409 agent_not_ready` card appears with action "Open workspace" linking to workspace switcher

### Requirement: Doctor rendering without [object Object]
Doctor SHALL render `checks` as flat rows (boolean→badge, string/number→mono
text) and render `diagnostics.{llm,qdrant,pdf_parser,vision}` in dedicated
sections with typed fields, never calling `String(object)`. It SHALL additionally
report optional-dependency status (Pillow, PyMuPDF, opendataloader-pdf,
python-docx, rasterio, shapely, geopandas, sqlite-vec, onnxruntime,
huggingface_hub) and SHALL NOT render GGUF model-path fields
(LLM/Embedding/Vision GGUF path) or the "Downloads require offline=false"
hint when online. Qdrant SHALL be reported as an optional backend, not a
requirement. Uncreated optional directories (e.g., `indexes` prior to indexing) and absent optional dependencies (such as Java when PyMuPDF fallback is available) SHALL be rendered as informative or neutral status, not hard red failures. Doctor SHALL provide an active "Test Connection" button for the configured LLM that invokes the probe endpoint and displays round-trip latency or error details.

#### Scenario: No object string
- **WHEN** Doctor is viewed with a workspace open
- **THEN** the DOM contains no text "`[object Object]`" and the diagnostics sections show `provider`, `model_id`, `key_configured`, `qdrant.reachable`, `pdf_parser.resolved`, `vision.checkpoint_exists` as primitives/badges

#### Scenario: Deps reported
- **WHEN** Doctor is viewed
- **THEN** the optional-dependency list reflects the runtime environment and Pillow/PyMuPDF/python-docx show installed

#### Scenario: No GGUF path fields
- **WHEN** Doctor or Settings is viewed
- **THEN** the DOM contains no "GGUF path" labels and no offline hint when `offline` is false

#### Scenario: Optional features distinguish unconfigured from failure
- **WHEN** Doctor is viewed in a fresh workspace without built indexes or Java runtime
- **THEN** missing Java displays PyMuPDF fallback active rather than a critical system failure, and uncreated indexes directory shows unbuilt status

#### Scenario: Active LLM test probe
- **WHEN** user clicks "Test Connection" on the LLM diagnostic card
- **THEN** the card displays reachability status, round-trip latency in milliseconds, or the exact network/auth error message

### Requirement: Workspace default UX
The workspace switcher SHALL offer `Workspaces` (resolved `GEOFOND_WORKSPACE`)
as default, auto-create it, and display the resolved absolute path. Closing/no
workspace SHALL show "No workspace open" with create/open affordance. When no
workspace is open the app SHALL show a setup wizard (create/open + LLM key +
base URL + embedding model) instead of the main shell, and the wizard SHALL
accept a parent directory path as well as the exact workspace path.

#### Scenario: First run no workspace
- **WHEN** the app loads with no workspace open
- **THEN** the header pill shows "workspace: closed" and the Overview empty state offers "Create in default Workspaces/"

#### Scenario: Setup wizard on closed workspace
- **WHEN** the app loads and `GET /api/v1/workspace` returns `status: closed`
- **THEN** the setup wizard renders with Create-new and Open-existing tabs
- **AND** the main shell is not reachable until a workspace is open

#### Scenario: Wizard exposes compute config
- **WHEN** the setup wizard opens
- **THEN** it shows an offline/online toggle (online default), an LLM
  provider selector (`api` default, `llamacpp`), an LLM base URL field, an
  LLM model id field, an LLM API key field, an embedding backend selector
  (`onnx` default), an embedding model id field, and a Hugging Face
  endpoint URL field (default `https://huggingface.co`)
- **AND** all of these are editable later on the Settings page

#### Scenario: Open by parent directory
- **WHEN** the user picks or types a folder that contains exactly one workspace
- **THEN** `POST /workspace/open` opens that workspace (200) without error

#### Scenario: Reload preserves open workspace
- **WHEN** the page reloads while a workspace is open
- **THEN** `GET /workspace` returns `status: open` with the same path and the Overview renders populated state

### Requirement: Settings Save works for canonical backends
`PUT /workspace/settings` SHALL accept `vector_backend: "sqlite-vec"` (the
canonical default) in addition to `qdrant`/`lancedb`/`numpy`; saving unchanged
defaults from the Settings page SHALL return 200, never `422`.

#### Scenario: Save with sqlite-vec
- **WHEN** the Settings page saves with `vector_backend: "sqlite-vec"`
- **THEN** the request is `200`, not `422`

#### Scenario: Save with qdrant
- **WHEN** the Settings page saves with `vector_backend: "qdrant"`
- **THEN** the request is `200`, not `422`

### Requirement: Online-first defaults and honest offline messaging
Creating a workspace SHALL default `offline` to `false`. Download affordances
SHALL be enabled and no offline hint shown when `offline` is false; when
`offline` is true downloads are disabled and the hint shows.

#### Scenario: Default offline flag
- **WHEN** a workspace is created with no explicit flag
- **THEN** `settings.offline` is `false`

#### Scenario: Offline hint visibility
- **WHEN** `offline` is `false`
- **THEN** download buttons are enabled and no offline hint shows
- **WHEN** `offline` is `true`
- **THEN** download buttons are disabled and the offline hint shows

### Requirement: Full web test coverage
The web app SHALL have a runnable test suite (Vitest unit + Playwright E2E
with screenshots) that verifies the setup wizard, workspace lifecycle,
settings save, doctor rendering, ingest/search/ask flow, RTL flip, and
empty/loading/error states against a live gateway.

#### Scenario: E2E smoke with screenshots
- **WHEN** the Playwright suite runs
- **THEN** it opens the app, captures a screenshot at each major step (wizard, overview, settings save, doctor, ingest, search, ask), and asserts no `[object Object]`, no 422 on save, and correct empty states

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

### Requirement: Grounded QA error and abstention surfacing
The Ask page SHALL surface the actual `abstention_reason` or error message returned by the gateway when the LLM is unavailable or abstains, rather than rendering only a generic configuration hint.

#### Scenario: Detailed abstention message rendered
- **WHEN** the Ask endpoint returns an abstention with a specific error message
- **THEN** the UI renders the exact failure reason in the message banner with action links to Settings

### Requirement: Expandable long text preview in search and asset cards
Text snippets on search hit cards, asset segment views, and Ask drawer source items SHALL provide a "Show more" / "Show less" toggle to expand clamped text.

#### Scenario: User expands long search hit
- **WHEN** a user clicks "Show more" on a search hit clamped to 4 lines
- **THEN** the full text of the segment is displayed without line clamping

### Requirement: Index manifest capability and strength indicator
The Index page SHALL fetch and display index manifest metadata including total vectors indexed, embedding dimension, build latency, last built timestamp, and active space ID.

#### Scenario: User inspects built index stats
- **WHEN** a user navigates to the Index page after building an index
- **THEN** the UI displays an index health card with vector count, vector dimension, and the verified active space ID

### Requirement: Free-text model download in settings
The Settings and Index pages SHALL offer a free-text input allowing users to enter any HuggingFace model repo identifier to initiate a download, and the "Scan Models" button SHALL actively invalidate and refetch the model query cache with loading feedback.

#### Scenario: Downloading model by repo ID
- **WHEN** a user enters a model identifier such as `sentence-transformers/all-MiniLM-L6-v2` into the download input and clicks Download
- **THEN** a background download job is triggered and the item appears in the progress list

### Requirement: Agent context scoping in chat
The Agent chat page SHALL provide an optional context picker allowing users to select collections or specific assets to scope the agent conversation.

#### Scenario: User scopes agent chat
- **WHEN** a user selects a collection from the context picker before sending a message
- **THEN** the selected collection ID is included in the chat request payload

### Requirement: Flexible farms registry discovery
The Farms page SHALL display farms from both filesystem GeoJSON files and database-stored vector layers, matching features by `farm_id`, `id`, `FID`, or case-insensitive variants, and providing a clear empty-state guide when no farm features are found.

#### Scenario: Ingested GeoJSON displays in farms registry
- **WHEN** a user opens the Farms page in a workspace containing an ingested GeoJSON layer with farm features
- **THEN** the registry table lists the features and enables farm report generation

### Studio UX acceptance — part 1

Launcher shall check conda/pnpm/curl before spawning, default to geo/5174 and require a healthy gateway. Settings and Ask shall disclose the workspace inference destination, never claim local-only inference, and display no active model for a closed workspace. Inverted or missing dates shall block scene searches with an inline explanation.

### Studio UX acceptance — part 2

A search without a region shall require explicit global consent. Downloads shall reuse the ROI, dates and sensor of their result set. Only generated scenes may display simulated previews, labelled as such. Sentinel-2 samples shall use S2 IDs on a five-day cadence. A filter miss shall offer clear-filter; an empty catalog result shall offer search guidance.

### Studio UX acceptance — part 3

Last 30 days shall include today and the previous 29 UTC dates. Failed basemaps shall be retryable without clearing drawn ROIs. ROI removal shall disclose linked-layer count and require confirmation. Rejected uploads shall retain individual reasons and accept a single validated replacement. Demo deletion shall identify the logical collection and asset path before ID-scoped removal.

### Studio UX acceptance — part 4

Abstention shall link to Resources and preserve the question in memory on return. Provenance shall copy the selected segment ID. A separate classifier confidence control shall not change QA grounding. Only accepted/corrected feedback counts toward the train action; zero shall link to review. Ops shall never infer successful LLM connectivity from configuration alone.

### Studio UX acceptance — part 5

SSE reconnection shall preserve job identity, last progress and event timestamp. Mobile and desktop navigation shall expose localized names and current page. The search shortcut shall match the platform. Model filtering shall not remove checked IDs. The custom connection wizard shall accept only operator-approved HTTPS bases and derive a distinct credential slot for each exact base; neither discovery nor activation shall reuse the previous provider key.

Live training shall track the gateway job by ID using the same SSE and snapshot handling as downloads. A failed, cancelled or unobserved job shall not produce a training success message or a simulated checkpoint; live progress shall not invent classifier accuracy or loss. Empty live asset, candidate and version inventories replace previous results.

### Second-pass Studio integrity requirements

- Navigation shall normalize unknown routes, preserve usable content at phone widths and handle Escape/Tab throughout the command dialog. Search commands debounce requests; selecting a segment opens its provenance, while Enter without a result does nothing.
- Production must not substitute example workspaces, ROIs, reviews, models, chat or playbooks for unavailable services. Workspace switching uses server-discovered paths and confirms the switch before reinitializing the client. Failed writes must not leave a successful review, rollback or ROI state. Diagnostics without measurements display unknown. Job details follow the visible selection. Live actions must not simulate server cancellation or retries.
- Chat preserves separate user and assistant identities and the gateway conversation ID. Unbacked citation references are removed. Playbook results remain available in full.
- Retrieval applies selected mode, collection IDs, geographic bounds and dates. Ask failures are visible and `min_score` can prevent generation. Citation chips resolve only to confirmed segment IDs. Absent confidence, duration, accuracy or solar elevation is not a zero measurement. Live model activity reflects the installed classifier per key.
- Acquisition preserves catalog timestamps and sensor identity, ROI statistics handle the antimeridian, text assets retain their type, and Settings reports effective origins/paths. Retired model shortcuts can be removed but not activated after discovery reports them absent.

### Third-pass Studio and acquisition integrity requirements

- A stored locale outside the supported set shall fall back to English instead of preventing mount, and preference-write failures shall not throw.
- Agent chat shall parse CRLF and multi-chunk SSE frames, keep the final snapshot instead of duplicating it, ignore composing Enter, and release the response reader when a consumer throws.
- Acquisition downloads shall be re-entrancy safe per scene and ROI, track jobs and preview layers by the ROI captured at click time, and shall not claim a preview band that the server did not return.
- Search that fails clears stale results and offers the error; a new ROI clears previous result and form state; dates carry accessible names; scene times are rendered in short form without dropping the day period.
- A finished ROI draft shall freeze further map clicks and hover previews until reset, the default ROI name derives from the workspace basename, and zero-area geometry cannot be saved.
- Unknown or absent timestamps render as an explicit dash rather than today's date, in both resource and model-version lists.
- Toasts announce politely, progress exposes an accessible value, the agent send control and ROI cancel control carry names, and repeated keydowns or IME composition shall not re-trigger shortcuts or submits.

### Fourth-pass Studio integrity requirements

- Coordinates render with hemisphere suffixes (`34.6°S`, `58.4°W`); a negative latitude or longitude is never labelled N/E and never printed as a bare negative number in the cursor readout, the ROI centroid card or agent confirmation text.
- Model rollback sends the full key (including `sub_region`) returned by `GET /models/versions`, so a sub-region model is rolled back rather than its sibling.
- Model-version rows remain distinguishable when two sub-regions share a version number.
