# MCP reference

Preferred MCP server entrypoint:

```bash
python3 -m mcp.brand_iterate_mcp
```

## Tool naming rules

Most CLI commands are auto-bridged into MCP tools using the command registry.

Mapping rule:

```text
bgen <command-name>  →  brand_<command_name>
```

Examples:

- `bgen show-session-summary` → `brand_show_session_summary`
- `bgen plan-material` → `brand_plan_material`
- `bgen update-messaging` → `brand_update_messaging`

Read-only inspection tools usually default to JSON output in the MCP bridge so hosts can consume them without extra `format=json` boilerplate.

## Custom MCP-only tools

Two tools are still intentionally custom instead of pure CLI passthroughs:

- `brand_pipeline` — one-call convenience tool for the full generative workflow
- `brand_inspire` — inspiration capture/list/configuration convenience tool

## Session start / onboarding tools

- `brand_list` — inspect saved brands before choosing a path
- `brand_use` — work directly against a saved brand
- `brand_create` — create a saved brand from a conversational brief
- `brand_start_testing` — create or switch to a sandboxed testing session
- `brand_show_session_summary` — confirm the active workspace after onboarding
- `brand_context_snapshot` — canonical machine-readable workspace context
- `brand_workspace_status` — canonical root + plugin/session alignment warnings
- `brand_capabilities` — material/model/tool surface and feature flags

Recommended start logic:

1. If a saved brand already exists, use `brand_use` or `brand_start_testing(brand=...)`.
2. If a repo/docs bundle exists but no saved brand yet, create/activate the workspace with `brand_init`, then use `brand_extract` and `brand_build_identity`.
3. If there is no brand yet, use `brand_create` for a durable saved brand or `brand_start_testing` for a temporary sandbox.

## Most important tools

### Context / inspection

- `brand_show_session_summary`
- `brand_context_snapshot`
- `brand_workspace_status`
- `brand_capabilities`
- `brand_show_blackboard`
- `brand_show_reference_analysis`
- `brand_show_iteration_memory`
- `brand_show_workflow_lineage`

### Planning / prompt inspection

- `brand_route_request`
- `brand_plan_material`
- `brand_plan_draft`
- `brand_critique_plan`
- `brand_build_generation_scratchpad`
- `brand_resolve_prompt`
- `brand_review_prompt`
- `brand_suggest_role_pack`
- `brand_suggest_layout`

### Generation / sets

- `brand_pipeline`
- `brand_generate`
- `brand_generate_once`
- `brand_plan_set`
- `brand_validate_brand_fit`
- `brand_validate_set`
- `brand_generate_set`
- `brand_derive_video`
- `brand_derive_mockup`

### Review / learning

- `brand_review`
- `brand_critique_rubric`
- `brand_submit_critique`
- `brand_feedback`
- `brand_compare`
- `brand_diagnose`
- `brand_evolve`
- `brand_improvement_questions`

### Inspiration / reference utilities

- `brand_extract_inspiration`
- `brand_consolidate_inspiration`
- `brand_capture_product`
- `brand_reference_rubric`
- `brand_submit_reference_analysis`
- `brand_example_sources`
- `brand_prompts_list`
- `brand_prompts_get`

## Host-plugin note

Pi and OpenClaw wrap this MCP backend and then expose their own higher-level host tools/actions on top.

Those host-layer tools are not part of the Python MCP server itself:

- Pi: `brand_search`, `brand_execute`, `brand_status`
- OpenClaw: `brand_search`, `brand_execute`, `brand_status`, `logo_execute`

## Registration

Use your MCP host’s normal stdio-server registration flow and point it at:

```bash
python3 -m mcp.brand_iterate_mcp
```
