# Specification: Agent Playbooks & Tool Execution Copilot

## Requirements

### Requirement 1: Playbooks Sidebar (`ZsVgP.jpg`)
The agent interface MUST feature a playbooks sidebar with domain-specific templates.

#### Scenario: Selecting a playbook
- **Given** the agent interface is active
- **When** the user clicks "Sentinel-2 NDVI Anomaly" playbook
- **Then** the chat initializes with the playbook's system context and sample parameter inputs
- **And** the playbooks rail marks the template as active.

### Requirement 2: Real-Time Tool Execution Cards
The system MUST display structured tool execution cards with live status badges during agent runs.

#### Scenario: Executing a tool step
- **Given** an agent loop is triggered
- **When** the agent invokes a tool (e.g., `data_engine.fetch_tiles`)
- **Then** a tool card renders with a pulsing `running` badge
- **And** upon completion, the badge turns green (`success`) with execution duration in milliseconds
- **And** the arguments and outputs can be expanded via disclosure toggle.

### Requirement 3: Living Artifact Cards
Agent tool outputs that produce data tables or spatial features MUST render as interactive living cards.

#### Scenario: Viewing tool output artifact
- **Given** a tool outputs a parcel summary table or GeoJSON
- **When** the message streams into the UI
- **Then** an interactive table or map preview card renders inside the message
- **And** the user can click "Pin to Map" to display the layer on the GIS map view.

### Requirement 4: Dual Layout (Full Page & Copilot Rail)
The agent experience MUST support both full-width workbench mode and persistent right-rail copilot mode.

#### Scenario: Toggling copilot rail
- **Given** the user is viewing the GIS Map page
- **When** clicking the "Agent Copilot" toggle in the top bar
- **Then** the agent drawer slides open from the right without navigating away from the map.
