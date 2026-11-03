# Proposal: agent-playbooks-copilot

## Why
Automating multi-step remote sensing analyses (e.g., METRIC ETa audits, NDVI anomaly detection, Sentinel-2 tile fetching) requires more than a simple text chat. As shown in mockup `ZsVgP.jpg`, technical users need a playbooks library, real-time step narration with tool execution status badges, collapsible arguments/outputs, and living interactive artifact cards rather than raw terminal output.

## What Changes
1. **Agent Playbooks Rail (`ZsVgP.jpg`)**:
   - Left-hand library of domain playbooks:
     - `Karkheh Basin ETa Audit`: Multi-temporal evapotranspiration water balance.
     - `Sentinel-2 NDVI Anomaly`: Anomaly detection across crop cycles.
     - `Thermal Calibration`: Land Surface Temperature radiometry check.
   - 1-click execution to prime the conversation with system instructions and required parameters.

2. **Step Narration & Tool Execution Cards**:
   - Real-time step-by-step tool checklist:
     - Tool name, description, duration, and status pill (`pending`, `running`, `success`, `error`).
     - Collapsible JSON inspection for invocation arguments and raw tool returns.

3. **Artifact-First Responses**:
   - Tools emit specialized artifact cards (summary data tables, raster preview cards, downloadable GeoJSON) embedded directly into the chat flow.
   - "Pin to Map" and "Export to Report" buttons on spatial artifacts.

4. **Copilot vs Full-Screen View**:
   - Agent can be opened as a dedicated full-screen workbench or toggled as a persistent right-rail copilot across other pages.

## Invariants & Guardrails
- Tool executions must run through `geoagent` public SDK and gateway APIs.
- Execution steps must stream via SSE (`/api/v1/events` or `/api/v1/agent/runs/{id}/stream`).
- Failure of an individual tool call must not crash the entire conversation stream; error states must render inside the tool card.
