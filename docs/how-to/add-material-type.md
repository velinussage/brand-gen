# Add a material type

1. Update `data/material_policy.json` with the new material's defaults, classifications, and any set-template relationships.
2. Update planning/generation logic if the new type needs special behavior:
   - `mcp/material_planning.py`
   - `mcp/generation_flow.py`
   - `mcp/reference_role_packs.py` or other review helpers if the type needs special role behavior
3. Add prompt/review fragments if the material needs new doctrine or quality rules.
4. Only touch `mcp/command_registry.py` or `mcp/cli_builders.py` if the new material type also requires a new command/flag surface.
5. Validate with `bgen types`, `bgen plan-material ...`, and `bgen pipeline ...`.
6. Add tests and update docs/skills if the new type changes user-visible behavior.
