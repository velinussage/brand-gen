---
name: brand-gen-setup
description: >
  Setup and installation skill for brand-gen. Use when the user wants to clone, install,
  configure, validate, or connect brand-gen to an agent host for the first time. Covers Python
  environment setup, .env configuration, agent-browser installation, MCP registration, and
  host-specific notes for Claude Code, Pi, OpenClaw, and CLI-first agents. After setup, load the
  main brand-gen skill for actual workflow guidance.
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Gen Setup

This skill covers installation, validation, and host wiring.

After setup is complete, load:

- `skills/brand-gen/SKILL.md` — main workflow
- `skills/brand-gen-reference/SKILL.md` — models, surfaces, file layout
- `skills/brand-gen-logo/SKILL.md` — logo workflows
- `skills/brand-content-ideation/SKILL.md` — messaging/copy ideation

## Prerequisites

- Python 3.11+
- a [Replicate API token](https://replicate.com/account/api-tokens)
- Node.js if using Pi, OpenClaw, or `agent-browser`

## Step 1 — clone and install

```bash
git clone <your-fork-or-repo-url>
cd brand-gen
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
bgen --help
```

If `bgen` is not found, activate the venv first.

## Step 2 — configure environment

```bash
cp .env.example .env
```

Set `REPLICATE_API_TOKEN` in `.env`.

Important notes:

- repo-local `.env` is the preferred config source
- a legacy host-specific fallback may still be read for compatibility
- set `BRAND_GEN_DIR` if you want durable state outside the repo checkout

## Local config

Create `.brand-gen-local.json` at the repo root. The agent should do this automatically:

1. Detect `repo_root` from the current working directory (`pwd`).
2. Ask the user: "Do you have an Obsidian vault or brand docs folder you want to connect? If so, what's the path?" If yes, add it to `vault_paths`. If no, set `vault_paths` to `[]`.
3. Write the file:
```json
{
  "repo_root": "<detected path>",
  "vault_paths": ["<user-provided path if any>"]
}
```

This file is only needed for Pi agents. If the user is CLI-only, skip this step.

Creative defaults (quality benchmarks, concept categories, metaphor vocabulary) are stored per-brand in `brand-profile.json` → `creative_context` and seeded on `bgen create-brand`.

### Verify creative_context

After creating or connecting a brand, verify `brand-profile.json` contains a `creative_context`
block. If missing (older brands or `extract-brand` workflows), the agent should create it with
defaults: `quality_benchmarks` from `.brand-gen-local.json` or `["Stripe", "Aesop", "Criterion",
"Muji"]`, `concept_categories` derived from the brand's `keywords`, `metaphor_vocabulary` empty.

## Step 3 — install recommended optional tools

| Tool | Install | Purpose |
|------|---------|---------|
| `agent-browser` | `npm install -g agent-browser && npx playwright install` | product screenshots and inspiration capture |
| `ffmpeg` | `brew install ffmpeg` / `apt install ffmpeg` | video → GIF helpers |
| `sips` | pre-installed on macOS | WEBP → PNG conversion |
| Google Chrome | normal browser install | HTML share-card PNG rendering |

`agent-browser` is treated as required by the validation script because capture/inspiration workflows depend on it, even though basic generation can run without it.

## Step 4 — validate

```bash
python3 scripts/validate_setup.py
```

This checks:

- required commands
- optional commands
- required env vars
- optional env vars
- which env files are being read

Fix any required missing items before moving on.

## Step 5 — connect to your agent

Start with the most generic option your host supports.

### CLI-first agents

Add instructions like:

```text
For brand material generation, use `bgen ...` or `python3 -m mcp.brand_iterate ...`.
Start by checking `bgen context-snapshot --format json`.
```

### Any MCP-compatible host

Run the stdio MCP server:

```bash
python3 -m mcp.brand_iterate_mcp
```

Register that command in your host’s normal MCP config.

### Claude Code

If your Claude setup expects copied local skills:

```bash
cp -r skills/brand-gen-setup/ ~/.claude/skills/brand-gen-setup/
cp -r skills/brand-gen/ ~/.claude/skills/brand-gen/
cp -r skills/brand-gen-reference/ ~/.claude/skills/brand-gen-reference/
cp -r skills/brand-gen-logo/ ~/.claude/skills/brand-gen-logo/
cp -r skills/brand-content-ideation/ ~/.claude/skills/brand-content-ideation/
cp -r skills/brand-gen-orchestration/ ~/.claude/skills/brand-gen-orchestration/

claude mcp add brand-gen -- python3 -m mcp.brand_iterate_mcp
```

Or add the MCP server manually to Claude’s config with `cwd` set to the repo root.

### Pi

Use the tracked package under `packages/pi-brand-gen/`.

Install Pi first using the official quickstart in the `badlogic/pi-mono` coding-agent README:

- https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md
- current install command: `npm install -g @mariozechner/pi-coding-agent`
- then either export an API key before running `pi`, or run `pi` and use `/login`

Typical local setup from the repo checkout:

```bash
cd packages/pi-brand-gen
npm install
npm run typecheck
```

Then register the local extension in Pi. Note that brand-gen's Pi integration currently ships from this repo checkout under `packages/pi-brand-gen/`; it is not yet a standalone published Pi package. Configure at least:

- `brandIterateMcpPath`
- optionally `brandGenDir`, `approvalMode`, `heartbeatIntervalMinutes`, `autoHeartbeat`

Important Pi note:

- the backend still reads the repo `.env`, so set `REPLICATE_API_TOKEN` there
- but Pi launches `python3 <brandIterateMcpPath>`, so the `python3` visible to Pi must have brand-gen's Python dependencies available

After Pi is wired up, verify with:

```text
/brand-gen status
/brand-gen brands
/brand-gen summary
```

If you need to change the active saved brand inside Pi, use:

```text
/brand-gen switch <brand>
```

Creating a new saved brand or starting a testing session is still CLI-first today:

```bash
bgen create-brand ...
bgen start-testing ...
```

See `packages/pi-brand-gen/README.md` for the current config and command surface.

### OpenClaw

Use the tracked package under `packages/openclaw-brand-gen/`.

Typical local setup from the repo checkout:

```bash
cd packages/openclaw-brand-gen
npm install
npm run typecheck
```

Then configure the plugin with at least:

- `brandIterateMcpPath`
- optionally `brandGenDir`, `logoIterateMcpPath`, `approvalMode`, `autoHeartbeat`

See `packages/openclaw-brand-gen/README.md` for the current config and tool surface.

## Loading the orchestration pipeline

For the full 6-phase generation pipeline (prepare → plan → validate → generate → critique → evolve), load `skills/brand-gen-orchestration/SKILL.md` after setup. This skill encodes the multi-agent quality workflow as sequential instructions any host can follow.

On OpenClaw, add it to your skills paths. On Claude Code, copy it to `~/.claude/skills/`. On CLI-first agents, reference it in your agent instructions.

## Step 6 — verify with a test run

```bash
bgen create-brand \
  --name "test-brand" \
  --description "A test brand for validating the setup" \
  --tone "calm,modern" \
  --palette "#336699"

bgen pipeline \
  --material-type x-feed \
  --goal "Validation run" \
  --mode hybrid \
  --format json

bgen show --format json --latest 1
```

If the pipeline completes and `show` returns a recent version, the install is working end to end.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `bgen: command not found` | activate the venv or re-run `python3 -m pip install -e .` |
| `REPLICATE_API_TOKEN not set` | check `.env` and re-run validation |
| `agent-browser: command not found` | `npm install -g agent-browser && npx playwright install` |
| MCP server exits immediately | run `python3 -m mcp.brand_iterate_mcp` directly from the repo root |
| OpenClaw plugin fails to start | check Node 22+, verify `brandIterateMcpPath`, and run `npm run typecheck` |
| `ModuleNotFoundError: No module named 'mcp'` | run from the repo root with the venv active, or reinstall editable mode |

## What to do next

Once setup is validated, load `skills/brand-gen/SKILL.md` for the real workflow.
