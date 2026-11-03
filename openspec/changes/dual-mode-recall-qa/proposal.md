# Proposal: dual-mode-recall-qa

## Why
Users need fast, zero-GPU answers when reviewing local remote sensing knowledge, with the option to escalate to multi-hop generative QA when an LLM is available. Furthermore, as illustrated in mockup `uBfSK.jpg`, scientific research requires a split view combining search hits, spatial polygon previews, sentence-level citation linking, and transparent abstention reasoning rather than speculative hallucinations.

## What Changes
1. **Search & Grounded QA Split Layout (`uBfSK.jpg`)**:
   - Left side: Query bar, filter chips (sensors: Landsat/Sentinel, collections, date range), and ranked hit list with similarity scores and vector polygon mini-thumbnails.
   - Right side: Grounded QA card featuring synthesized or recalled answer text, confidence metric badge, and answer mode toggle (`fast recall` vs `slow synthesis`).

2. **Dual-Path Recall Engine**:
   - `Fast Recall` mode (`model: recall`): Completely local, zero-LLM extractive recall assembling top semantic segments into structured citations under 50ms.
   - `Slow Synthesis` mode (`grounded_qa`): Uses local GGUF or remote OpenAI-compatible API to generate narrative synthesis strictly grounded in retrieved segments.

3. **Citation & Provenance Drawer**:
   - Inline sentence-level citation pills (e.g., `[1]`, `[2]`).
   - Clicking a citation opens a slide-over provenance drawer displaying:
     - Exact highlighted snippet text and segment locator.
     - Source asset name, collection, file path.
     - SHA-256 verification hash and provenance chain (Answer → Citation → Segment → Asset → SHA-256).

4. **First-Class Abstention Diagnostics**:
   - Dedicated diagnostic alert when confidence score falls below threshold or when no local sources match.
   - Actionable diagnostics: indicates missing sensors, spatial bounds mismatch, or recommendation to ingest additional files.

## Invariants & Guardrails
- Fast recall MUST work without any LLM API key or local model download.
- Provenance chain must remain verifiable back to asset revision SHA-256.
- Abstention must never crash or produce a raw error modal; it must render as a structured state.
