# Tasks: agent-playbooks-copilot

- [ ] 1. Playbooks Library UI
  - [ ] 1.1 Create `PlaybookList.tsx` component with category badges and search.
  - [ ] 1.2 Wire playbook selection to pre-fill prompt context and parameters.
- [ ] 2. Tool Execution Cards (`ZsVgP.jpg`)
  - [ ] 2.1 Build `ToolExecutionCard.tsx` with status pills (`running`, `success`, `error`), timing, and expandable JSON viewer.
  - [ ] 2.2 Wire SSE event stream to update tool card states in real-time.
- [ ] 3. Living Artifact Renderers
  - [ ] 3.1 Build `TableArtifactCard.tsx` for tabular tool outputs.
  - [ ] 3.2 Build `SpatialArtifactCard.tsx` with "Pin to Map" and "Export GeoJSON" actions.
- [ ] 4. Copilot Drawer Integration
  - [ ] 4.1 Build `AgentCopilotDrawer.tsx` that can overlay any screen.
  - [ ] 4.2 Sync active workspace and document context between active page and copilot drawer.
- [ ] 5. Testing & Verification
  - [ ] 5.1 Unit tests for `ToolExecutionCard` state transitions.
  - [ ] 5.2 Verification of playbook invocation and artifact rendering.
