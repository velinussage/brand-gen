# Add a model backend

1. Update `mcp/models.json` with the new backend definition.
2. Add or update presets in `mcp/presets.json` if the backend needs tuned defaults.
3. Ensure `mcp/generate.py` can shape provider-specific inputs and parse outputs correctly.
4. Validate with `build-generation-scratchpad` + `generate` or `pipeline`.
5. Update docs/skills if the new backend changes the recommended workflow or model-selection guidance.
