## ADDED Requirements

### Requirement: Multipart and JSON client serialization
The web HTTP client SHALL detect `FormData` payloads and omit the `Content-Type` header to allow the browser to supply the correct multipart boundary, while setting `Content-Type: application/json` for non-FormData request bodies.

#### Scenario: Ingest file upload serialization
- **WHEN** the user uploads a file through the Ingest page or dropzone
- **THEN** the request to `POST /api/v1/ingest` is sent with the browser's generated `multipart/form-data; boundary=...` header and accepted by the gateway with `202 Accepted`

### Requirement: End-to-end verified interaction paths
All interactive buttons, forms, and toggles across all 18 web routes SHALL execute without unhandled Promise rejections, blank screens, or silent HTTP 4xx/5xx failures.

#### Scenario: Ingest flow execution
- **WHEN** the user selects a target collection and drops or selects a supported file (`.md`, `.pdf`, `.txt`, etc.)
- **THEN** an upload job is created, the job polling shows progress, and a success or duplicate summary banner is rendered
