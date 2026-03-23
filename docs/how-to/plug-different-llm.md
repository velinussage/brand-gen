# Plug in a different LLM

brand-gen uses hosted LLM/VLM calls mainly for routing, planning review, critique, and image/reference analysis.

To swap providers:

1. update the task-specific call sites (typically `mcp/material_planning.py`, `mcp/vlm_critique.py`, or `mcp/reference_analysis.py`)
2. keep the downstream response shapes stable for `review-prompt`, `critique-plan`, critique ingestion, and reference-analysis flows
3. validate the affected flows end to end, not just the raw API call

Notes:

- the old generic `_llm_text_complete()` helper is gone; current integrations are task-specific
- if the provider changes token limits or response structure, check prompt budgeting and review/routing heuristics too
