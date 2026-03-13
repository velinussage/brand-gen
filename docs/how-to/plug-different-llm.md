# Plug in a different LLM

brand-gen uses hosted LLM/VLM calls mainly for routing, critique, and image analysis.

To swap providers:
1. update the relevant request logic in `mcp/brand_iterate.py`
2. keep the response shape stable for downstream code
3. validate `review-prompt`, critique, and reference-analysis flows

Note: the old `_llm_text_complete()` helper has been removed; current integrations are task-specific.
