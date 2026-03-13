# Contributing to brand-gen

Thanks for your interest in contributing! This guide covers how to set up, test, and submit changes.

## Quick setup

```bash
git clone https://github.com/yourorg/brand-gen.git
cd brand-gen
cp .env.example .env
# Fill in REPLICATE_API_TOKEN
python3 scripts/validate_setup.py
```

## Development

### Running tests

```bash
python3 -m pytest tests/ -v
```

### Linting / compile check

```bash
python3 -m py_compile mcp/brand_iterate.py
python3 -m py_compile mcp/brand_iterate_mcp.py
python3 -m py_compile mcp/pipeline_runner.py
python3 -m py_compile mcp/pipeline_types.py
python3 -m py_compile mcp/route_predicates.py
```

### Running the MCP server locally

```bash
python3 mcp/brand_iterate_mcp.py
```

### Running the CLI

```bash
python3 mcp/brand_iterate.py --help
```

## Project structure

```
mcp/                 # Core Python — CLI + MCP server + pipeline
  brand_iterate.py   # Main CLI and all commands (~7500 lines)
  brand_iterate_mcp.py  # MCP server (stdio JSON-RPC)
  pipeline_types.py  # Typed dataclass schemas
  pipeline_runner.py # Pipeline orchestrator
  route_predicates.py # Scored predicate routing
  generate.py        # Replicate API wrapper
  models.json        # Model registry
  presets.json       # Generation presets
scripts/             # Standalone helper scripts
skills/              # Agent skill files (SKILL.md)
prompts/             # Prompt templates and briefs
data/                # Static data (example sources, review rules, role packs)
packages/            # Integration bridges (Pi, OpenClaw)
tests/               # Python tests
docs/                # Documentation
```

## Submitting changes

1. Fork the repo and create a feature branch
2. Make your changes
3. Run tests and compile checks
4. Submit a PR with a clear description of what changed and why

### PR guidelines

- One logical change per PR
- Include test coverage for new commands or pipeline stages
- Keep `brand_iterate.py` changes focused — it's already large, avoid adding unrelated features
- Update skill files (`skills/brand-gen/SKILL.md`) if you add or change CLI commands or MCP tools

## Adding a new material type

1. Add the type key to `SUPPORTED_MATERIAL_TYPES` in `brand_iterate.py`
2. Add a `material_dna` entry with default policy (mode, model, aspect ratio, product truth expression)
3. Add any material-specific doctrine snippets to `brand-identity.json` under `material_dna`
4. Update `skills/brand-gen/SKILL.md` if the new type changes routing or has non-obvious constraints
5. Add a test in `tests/` that validates the type routes and plans correctly

## Adding a new model backend

1. Add the model entry to `mcp/models.json`
2. Add generation presets to `mcp/presets.json` if needed
3. Update `mcp/generate.py` with the Replicate API call
4. Update `skills/brand-gen-reference/references/models.md`
5. Test with a real generation to verify output format

## Code style

- Python 3.10+ (uses `match` statements and `str | None` union syntax)
- No external dependencies in `mcp/brand_iterate.py` beyond stdlib + `requests`
- Use `--format json` in new commands to return structured data
- Prefer returning data to stdout over writing files when practical

## Questions?

Open an issue for discussion before starting large changes.
