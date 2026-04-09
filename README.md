# brand-gen

> Give your AI agent a brand designer. Generate, critique, and iterate brand materials through conversation.

brand-gen is a local, file-backed toolkit that an AI agent can use to understand a brand, plan materials, generate assets, review them, and learn over time. It works with any agent that has shell access — CLI-first agents, MCP hosts, Pi, OpenClaw, Claude Code, Codex, or Cursor.

![brand-gen generated storyboard](docs/assets/example-v14-storyboard.jpg)

## Install

```bash
git clone https://github.com/velinussage/brand-gen.git
cd brand-gen
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e .
cp .env.example .env          # add your REPLICATE_API_TOKEN
python3 scripts/validate_setup.py
```

**Requirements:** Python 3.11+ and a [Replicate API token](https://replicate.com/account/api-tokens).

## Quick start

```bash
# Create a brand
bgen create-brand \
  --name "Acme" \
  --description "Operational software for modern field teams" \
  --tone "calm,technical,trustworthy" \
  --palette "#1A6B6B,#C85A2A"

# Generate a first asset
bgen pipeline \
  --material-type x-feed \
  --goal "Launch announcement" \
  --mode hybrid \
  --format json

# Review and iterate
bgen feedback v1 --score 4 --notes "Strong direction, simplify the copy"
bgen pipeline --material-type x-feed --source-version v1 --format json
```

Or just tell your agent what you want:

```text
Read skills/brand-gen/SKILL.md, then run: bgen context-snapshot --format json
```

## How it works

```text
You → "Make a launch card for our product announcement"
       ↓
Agent → context-snapshot / route-request / pipeline
       ↓
brand-gen → plan → critique → scratchpad → generate → v1.png
       ↓
You → "The hierarchy is better, but the copy is too dense"
       ↓
Agent → critique-rubric → submit-critique → feedback → iterate
```

The default pipeline follows a planning-first model — explore workspace, route request, draft plan, critique plan, then generate. No freehand generation until the plan is approved.

## Skills

brand-gen ships as skill files any agent can read. No host-specific plugin required.

| Skill | Purpose |
|-------|---------|
| `skills/brand-gen-setup/SKILL.md` | First-time install and host wiring |
| `skills/brand-gen/SKILL.md` | Workspace, planning, generation, review, iteration |
| `skills/brand-gen-orchestration/SKILL.md` | Full 6-phase generation pipeline with quality gate |
| `skills/brand-gen-reference/SKILL.md` | Model specs, surface dimensions, file layout |
| `skills/brand-gen-logo/SKILL.md` | Logo and wordmark workflows |
| `skills/brand-content-ideation/SKILL.md` | Messaging and copy ideation |

## Core capabilities

- **One-call pipeline**: route → plan → critique → scratchpad → generate
- **Durable brand memory**: saved profiles, identity, blackboard, iteration memory, and learnings
- **Review loop**: rubric-first critique, scoring, feedback, and evolution analysis
- **Multiple onboarding paths**: saved brand, repo extraction, conversational brief, or testing session
- **Messaging system**: ideate, persist, and promote approved copy across sessions
- **HTML share cards**: deterministic rendering with plugin-based data fetching and headless Chrome export
- **Derivatives**: extend approved stills into mockups or short-form video
- **Reference workflows**: capture product screenshots, consolidate inspiration, assign reference roles

## Connect to your agent

The simplest path — tell your agent to read the skill files:

```text
Read these skill files and follow them for brand material work:
- skills/brand-gen-setup/SKILL.md (first-time only)
- skills/brand-gen/SKILL.md (workspace + workflow)
- skills/brand-gen-orchestration/SKILL.md (generation pipeline)

Start by running: bgen context-snapshot --format json
```

For MCP integration:

```bash
python3 -m brand_gen.brand_iterate_mcp    # stdio MCP server
```

See [docs/host-setup.md](docs/host-setup.md) for Claude Code, Pi, and OpenClaw setup.
See [docs/starter-prompts.md](docs/starter-prompts.md) for copy-paste prompts to bootstrap your agent.

## Documentation

- [Getting Started](docs/getting-started.md) — clone to first asset
- [Architecture](docs/architecture.md) — runtime layers, state model, command registry
- [CLI Reference](docs/cli-reference.md) — full command list
- [MCP Reference](docs/mcp-reference.md) — tool naming and custom tools
- [Host Setup](docs/host-setup.md) — Claude Code, Pi, OpenClaw integration
- [Starter Prompts](docs/starter-prompts.md) — copy-paste agent prompts
- [Concepts](docs/concepts.md) — workspace, brands, sessions, blackboard
- [Skills](docs/skills.md) — loading order and skill details
- [Limitations](docs/limitations.md)

## Example output

![brand-gen generated brand scene](docs/assets/example-v028-brand-scene.jpg)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

MIT
