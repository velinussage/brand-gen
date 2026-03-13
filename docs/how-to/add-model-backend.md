# Add a model backend

1. Update `mcp/models.json` with the new backend definition.
2. Add presets to `mcp/presets.json` if needed.
3. Ensure `mcp/generate.py` can shape provider-specific inputs.
4. Validate via `build-generation-scratchpad` + `generate`.
