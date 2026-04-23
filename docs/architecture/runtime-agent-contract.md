# Runtime and agent contract

This file is the architecture contract for host adapters and specialist agents. Prefer updating this contract over scattering new runtime rules through long agent prompts.

## Runtime root

- The canonical runtime root is the brand-gen data directory, usually `<repo>/.brand-gen` for this checkout or `~/.brand-gen` for a global install.
- `BRAND_GEN_DIR` must point at that runtime root, not at the source repository. The Python runtime canonicalizes a repo-root override to `<repo>/.brand-gen` when it can prove that layout, but configs should still use the explicit runtime path.
- `bgen workspace-status --format json` is the authoritative health check. A healthy local checkout reports `plugin_matches_python_workspace: true`, `plugin_matches_python_root: true`, and no warnings.

## Typed tool surface

- Host adapters expose 44 canonical `brand_*` tools from `packages/brand-gen-core/src/tool-registry.ts`.
- The soft cap is 45 tools. Add a new verb only when it is a narrow primitive that agents can call directly.
- When adding or removing a canonical tool, update these files together:
  1. `packages/brand-gen-core/src/tool-registry.ts`
  2. `brand_gen/mcp_bridge_registry.py`
  3. `brand_gen/policy.py::POLICY_CLASSES_BY_TOOL`
  4. `brand_gen/agent_specialization.py` if any specialist should call it
  5. mirrored agent frontmatter in `.claude/agents/`, `.pi/agents/`, and `skills/brand-gen/claude-agents/`

## Pi agents

Pi agents are typed-tool-only.

- Do not embed shell procedures or raw CLI workflows in `.pi/agents/brand-*.md`.
- Use the `tools:` frontmatter as the runtime contract.
- If an agent needs a capability that is only documented as a CLI command, promote it to a canonical `brand_*` verb or keep it as an explicit operator fallback outside the Pi agent body.

## Exact text generation

Native image generation is not a deterministic text renderer.

- Plans that request exact/verbatim visible text must declare a deterministic strategy.
- Valid deterministic paths include `render_backend: "html"` or an explicit HTML/SVG/composite text strategy.
- Without that strategy, plan validation and scratchpad assembly block generation before tokens are spent.

## Material taxonomy

Deprecated material labels are migrated by `brand_gen/material_taxonomy_migration.py` and the `migrate-material-taxonomy` CLI.

- Run `bgen report-material-taxonomy --all-saved --include-sessions --format json` before and after migration.
- A clean workspace reports `deprecated_usage_count: 0`.
- The migrator rewrites top-level plans/manifests plus nested plan wrappers, critiques, learning rollups, and memory files.
