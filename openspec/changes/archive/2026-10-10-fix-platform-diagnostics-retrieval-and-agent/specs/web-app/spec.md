# Spec Delta: web-app

## MODIFIED Requirements

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

## ADDED Requirements

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
