# MCP reference

The MCP server is `mcp/brand_iterate_mcp.py`.

## Session start / onboarding tools

- `brand_list_brands` — inspect saved brands before choosing a path
- `brand_use` — work directly against a saved brand
- `brand_start_testing` — create or switch to a sandboxed testing session
- `brand_show_session_summary` — confirm the active workspace after onboarding

Recommended start logic:
1. If a saved brand already exists, use `brand_use` or `brand_start_testing(brand=...)`.
2. If a repo/docs bundle exists but no saved brand yet, create/extract via CLI first, then come back to MCP tools.
3. If there is no brand yet, start a testing session and build the session profile/identity from conversation before generating.

## Most important tools

- `brand_pipeline` — one-call generative workflow
- `brand_show_session_summary` — current workspace summary
- `brand_show` — manifest inspection
- `brand_show_blackboard` — blackboard state
- `brand_ideate_messaging` — returns context for agent-generated messaging angles
- `brand_update_messaging` — persists approved messaging
- `brand_plan_set` / `brand_validate_set` / `brand_generate_set` — set workflows

## Registration

Use your MCP host’s normal stdio-server registration flow and point it at:

```bash
python3 mcp/brand_iterate_mcp.py
```
