# Proposal: design-system-instrument

## Why
GeoMind's current web interface uses a generic gray card layout that feels like an internal scaffold rather than a startup-grade scientific instrument. To match the visual specification defined in mockups `KwzrE.jpg` (Workspace Setup) and `lQSVu.jpg` (Dashboard), we need to establish an emerald/teal precision design system, an icon-rail navigation shell with top search bar, a split-view workspace modal with sample onboarding, and sparkline metric cards.

## What Changes
1. **Design System & Tokens**:
   - Update `index.css` palette to deep teal-emerald accent (`#00876c` / `#0f766e`), slate borders (`#e2e8f0` / dark `#1e293b`), off-white background (`#f8fafc` / dark `#090d16`).
   - Standardize tabular monospace for metrics, hashes, coordinates, and dates.
   - Enforce RTL-safe logical properties (`ps/pe/ms/me`).

2. **Application Shell & Navigation**:
   - Modern icon-rail / compact sidebar with active indicator pills and status icon.
   - Top header with prominent search / ⌘K command trigger, active workspace indicator, and quick action buttons.

3. **Workspace Setup Modal (`KwzrE.jpg`)**:
   - Split modal dialog:
     - Left pane: search filter, existing workspaces list sorted by last opened, active status pill.
     - Right pane: directory path selector, name input, embedding model selection, LLM provider settings, and 1-click "Load Demo Workspace (Karkheh Basin)" button.

4. **Home / Overview Dashboard (`lQSVu.jpg`)**:
   - Metric cards with mini SVG sparkline trends: Indexed Assets, Stored Vectors, Active Playbooks, Engine Health.
   - Recent activity stream with event type badges and timestamp formatting.
   - Quick action shortcuts grid (Ingest Folder, Run Playbook, Fast Recall).

## Invariants & Guardrails
- Apps consume only gateway HTTP API (`/api/v1`).
- All user-facing strings must support English and Persian (`en`/`fa`) via i18next.
- Strict typing (TypeScript strict mode, zero `any`).
- Responsive layout supporting both desktop instrument density and mobile viewports.
