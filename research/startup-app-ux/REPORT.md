# Startup-Grade GeoMind Product & UX Report

Date: 2026-11-03

## Executive summary
GeoMind can become a real startup product by focusing on three user outcomes:
1. Reach a cited answer over local data in under 5 minutes.
2. Make provenance and abstention first-class, not afterthoughts.
3. Close the feedback loop into visible learning.

## Personas
- **Researcher (primary)**: needs cited answers, not raw imagery. [1][3][4]
- **GIS/EO analyst**: hybrid code + maps; needs validation judgment and provenance. [6][8]
- **Data engineer**: ingest, index, batch; needs reliability and status. [2]
- **Decision-maker**: needs actionable intelligence, not datasets. [4][10]

## Jobs-to-be-done
- "When I have a folder of papers/rasters, help me ask a question and get a cited answer."
- "When the model is unsure, tell me and show sources."
- "When I give feedback, turn it into better answers."
- "When offline, keep working from local data."

## Competitive UX patterns to adopt
- Code+map+tabbed panels (Earth Engine) [F2]
- Plain-language step narration; results as live layers (Felt AI) [F2]
- Chat+table+map triad; answers as persistent artifacts [F2]
- MCP exposure for distribution [F2]
- Error→assistant bridge [F2]

## Trust & provenance UX
- Claim-level AND answer-level citations [F3]
- Span-level linking to exact passage [F3]
- Explicit missing/broken citation handling [F3]
- Per-claim grounding states: fully cited / synthesis-informed / uncited [F3]
- Verification step between generation and render [F3]
- Trust calibration: expose uncertainty, graduated autonomy [F3]

## Local-first UX
- Instant open, no blocking spinners [F4]
- Sync status visible; refuse partial render [F4]
- Quick capture; exclusions; exportable formats [F4]
- Offline-by-default; model management UI [F4]

## Onboarding & empty states
- Instructional empty states on every surface [F5]
- "Try sample workspace" seeded with Landsat + papers + cited Q&A [F5]
- Distinct "required configuration" state for unconfigured LLM [F5]
- Welcome modal + dismissible checklist (3-5 items) [F5]
- Behavior-triggered 3-tooltip tour [F5]

## Prioritized user stories (MVP)
1. As a researcher, I open a sample workspace and ask a question, then see a cited answer in <60s.
2. As a researcher, when no LLM is configured, I still get recall snippets with sources.
3. As an analyst, I view citations as chips that open the exact segment.
4. As a user, every empty page tells me the next action.
5. As a user, I can jump anywhere via Ctrl/Cmd+K.
6. As a user, I can switch Simple/Advanced mode and it persists.

## Advanced (post-MVP)
- Agent copilot rail with tool trace.
- Feedback loop pipeline visualization.
- Map-first home with live overlay.
- Provenance drawer (answer→citation→segment→asset→SHA-256).
- Multi-workspace management.

## Open questions
- Should sample workspace auto-create or require click? (recommend click)
- Should command palette include actions or navigation only? (recommend nav only v1)
