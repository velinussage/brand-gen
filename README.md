# brand-gen

> Agent-driven brand material experimentation toolkit

Generate, critique, and iterate brand materials — social cards, browser illustrations, banners,
posters, motion assets, and brand systems — using stored brand memory plus agent-friendly CLI and
MCP surfaces.

## Install

### Prerequisites
- Python 3.11+
- A Replicate API token for generative runs
- Optional: an MCP host if you want tool-mode use instead of CLI-only use

### Setup
```bash
git clone <your-fork-or-repo-url>
cd brand-gen
cp .env.example .env
python3 scripts/validate_setup.py
```

## Quick start

Choose the right onboarding path first:

- **Existing saved brand** → `list-brands`, then `use <brand-key>` or `start-testing --brand <brand-key>`
- **Repo/docs bundle but no saved brand yet** → `init --brand-name`, then `extract-brand`, then `use`
- **No brand yet** → `start-testing --working-name`, gather product truth from conversation, then rebuild the session identity

```bash
# Existing brand
python3 mcp/brand_iterate.py list-brands --format json
python3 mcp/brand_iterate.py use <brand-key>

# Or new brand from a project
python3 mcp/brand_iterate.py init --brand-name acme
python3 mcp/brand_iterate.py extract-brand --project-root /path/to/project --brand-name acme
python3 mcp/brand_iterate.py use acme

# Then generate a first social asset
python3 mcp/brand_iterate.py pipeline --material-type x-feed --mode hybrid --format json
python3 mcp/brand_iterate.py show-session-summary --format json
```

## Important skills

- `skills/brand-gen/SKILL.md` — main workflow skill; use this first for most sessions
- `skills/brand-gen-reference/SKILL.md` — on-demand reference pack for models, surfaces, and file layout
- `skills/brand-gen-logo/SKILL.md` — separate workflow for logo / wordmark / lockup exploration

## Core features

- one-call generative pipeline: route → plan → critique → scratchpad → generate
- session-scoped iteration memory with promotion into saved brand memory
- manifest/versioning with feedback, compare, and evolve flows
- reference-role packs and reference analysis for stronger planning
- MCP server for agent use plus plain CLI for direct scripting
- optional Pi/OpenClaw integration packages under `packages/`

## Main surfaces

### CLI
```bash
python3 mcp/brand_iterate.py <command> ...
./bin/brand-iterate <command> ...
```

### MCP server
```bash
python3 mcp/brand_iterate_mcp.py
./bin/brand-mcp
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Concepts](docs/concepts.md)
- [CLI Reference](docs/cli-reference.md)
- [MCP Reference](docs/mcp-reference.md)
- [Skills](docs/skills.md)
- [Limitations](docs/limitations.md)
- [How to add a material type](docs/how-to/add-material-type.md)
- [How to add a model backend](docs/how-to/add-model-backend.md)
- [How to plug in a different LLM](docs/how-to/plug-different-llm.md)
- [How to write an agent skill](docs/how-to/write-agent-skill.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

MIT
