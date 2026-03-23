# Limitations

Known limitations:

- `mcp/brand_iterate_mcp.py` still carries two intentional custom MCP handlers (`brand_inspire`, `brand_pipeline`) instead of being a pure CLI passthrough surface
- generation test coverage is still mostly structural/unit level; external model execution is not fully mocked end-to-end
- some policy/default behavior is still hardcoded in Python and JSON data instead of being fully data-driven per brand
- HTML share cards require Google Chrome for headless PNG rendering
- share-card platform plugin coverage is still limited; the repo ships one example plugin (Sage Protocol) alongside the generic web fallback
- governed/source-text extraction is still imperfect when the source page is procedural, navigation-heavy, or weakly structured
- visual quality validation is still partly agent/manual even though QA packets, critique artifacts, and blackboard learning have improved
- the runtime still reads some host-specific legacy env/config fallbacks for compatibility, so you may still see historical `.claude` wording in a few internal paths/messages

## Architecture status

- Preferred entrypoints are:
  - `bgen ...`
  - `python3 -m mcp.brand_iterate ...`
  - `python3 -m mcp.brand_iterate_mcp`
- `brand-iterate` remains a legacy alias and still works
- legacy file-path CLI invocation remains compatibility-only
- `mcp/brand_iterate.py` is a thin shim; business logic lives under `mcp/*`
- `mcp/legacy_api.py` remains only as an external compatibility shim
- `packages/brand-gen-core/` is now the shared TypeScript data/runtime layer for native host integrations
- notes under `docs/plans/`, `docs/brainstorms/`, and `docs/scratchpad/` are historical working docs, not the current public API reference
