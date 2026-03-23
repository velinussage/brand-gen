# Contributing to brand-gen

Thanks for your interest in contributing. This guide covers setup, testing, architecture touchpoints, and PR expectations.

## Quick setup

```bash
git clone https://github.com/yourorg/brand-gen.git
cd brand-gen
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e ".[dev]"
cp .env.example .env
python3 scripts/validate_setup.py
```

Fill in `REPLICATE_API_TOKEN` in `.env`. If you want durable state outside the repo checkout, set `BRAND_GEN_DIR` too.

## Development

### Running tests

```bash
python3 -m pytest tests/ -v
```

### Compile / type checks

```bash
python3 -m compileall mcp scripts
```

If you touch the TypeScript host packages, run checks in the package you changed:

```bash
cd packages/brand-gen-core && npm install && npm run typecheck
cd packages/pi-brand-gen && npm install && npm run typecheck
cd packages/openclaw-brand-gen && npm install && npm run typecheck
```

### Running the MCP server locally

```bash
python3 -m mcp.brand_iterate_mcp
```

### Running the CLI

```bash
bgen --help
brand-iterate --help          # legacy alias, still works
python3 -m mcp.brand_iterate --help
```

## Project structure

```text
mcp/                      Core Python runtime — CLI, MCP server, planning, generation, review
  brand_iterate.py        Thin compatibility shim for legacy file-path execution
  cli.py                  Package-first CLI entrypoint
  brand_iterate_mcp.py    MCP server wrapper
  commands/               Command handlers grouped by domain
  command_registry.py     Single source of truth for command registration
  cli_builders.py         CLI flag builders
  mcp_bridge_registry.py  CLI→MCP bridge schema generation
  share_card_renderer.py  HTML share-card facade and plugin registry
data/                     Material policy, prompt fragments, role packs, routing rules, examples
prompts/                  Prompt templates and system prompt fragments
skills/                   Agent skill files (public repo skills)
scripts/                  Supporting scripts and compatibility wrappers
packages/brand-gen-core/  Shared TS layer for host plugins (workspace, journal, context, heartbeat)
packages/pi-brand-gen/    Pi host integration
packages/openclaw-brand-gen/ OpenClaw host integration
tests/                    Python tests
docs/                     User-facing docs and historical planning notes
```

## Submitting changes

1. Fork the repo and create a feature branch
2. Make your changes
3. Run the relevant tests/checks
4. Update docs/skills/package READMEs when you change user-facing behavior
5. Submit a PR with a clear description of what changed and why

### PR guidelines

- Keep one logical change per PR when possible
- Include tests for new commands, pipeline stages, or host-package behavior
- Prefer cohesive helpers/modules over growing compatibility shims
- If you change CLI or MCP behavior, update the matching docs under `docs/` and any affected skill files under `skills/`
- If you change Pi/OpenClaw behavior, update the package README in `packages/`

## Adding a new material type

1. Update `data/material_policy.json` with the material defaults/classifications
2. Update planning/execution code as needed (`mcp/material_planning.py`, `mcp/generation_flow.py`, related review/prompt helpers)
3. Update reference-role-pack or prompt-fragment data when the new type needs new behavior
4. Update `mcp/runtime_models.py`-driven assumptions only when the data model needs a new helper path
5. Add tests in `tests/`
6. Update docs and any affected skills

## Adding a new model backend

1. Add the model entry to `mcp/models.json`
2. Add presets to `mcp/presets.json` if needed
3. Update `mcp/generate.py` with provider-specific shaping/calls
4. Update reference docs/skills if the model changes recommended workflows
5. Test with a real generation when practical

## Code style

- Python 3.11+ for the main runtime
- Prefer package-first execution and imports:
  - `bgen ...`
  - `python3 -m mcp.brand_iterate ...`
  - `python3 -m mcp.brand_iterate_mcp`
- `brand-iterate` remains as a legacy alias and still works
- Treat `python3 mcp/brand_iterate.py ...` as compatibility-only
- Prefer returning structured data (`--format json`) for new commands and MCP-facing surfaces
- Avoid hardcoded machine-specific paths in docs, skills, prompts, and examples; prefer env vars or placeholders

## Questions?

Open an issue for discussion before starting large changes.
