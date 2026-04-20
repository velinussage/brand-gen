# Host setup

brand-gen works with any agent that can run shell commands. Host-specific plugins add convenience (widgets, heartbeats, MCP bridges) but are not required.

## Any agent (skill files only)

Tell your agent to read the skill files:

```text
Read these skill files and follow them for brand material work:
- skills/brand-gen-setup/SKILL.md (first-time only)
- skills/brand-gen/SKILL.md (workspace + workflow)
- skills/brand-gen-orchestration/SKILL.md (generation pipeline)

Start by running: bgen context-snapshot --format json
```

This works on Claude Code, Codex, OpenClaw, Cursor, or any agent with shell access.

## MCP server

Run the MCP server as stdio:

```bash
python3 -m brand_gen.brand_iterate_mcp
```

Most tools are exposed with a `brand_` prefix:

- `bgen show-session-summary` → `brand_show_session_summary`
- `bgen plan-material` → `brand_plan_material`
- `bgen feedback` → `brand_feedback`

See [mcp-reference.md](mcp-reference.md) for naming rules and custom MCP-only tools.

## Claude Code

Copy skills into Claude's skill directory and register the MCP server:

```bash
cp -r skills/brand-gen-setup/ ~/.claude/skills/brand-gen-setup/
cp -r skills/brand-gen/ ~/.claude/skills/brand-gen/
cp -r skills/brand-gen-reference/ ~/.claude/skills/brand-gen-reference/
cp -r skills/brand-gen-logo/ ~/.claude/skills/brand-gen-logo/
cp -r skills/brand-content-ideation/ ~/.claude/skills/brand-content-ideation/
cp -r skills/brand-gen-orchestration/ ~/.claude/skills/brand-gen-orchestration/

claude mcp add brand-gen -- python3 -m brand_gen.brand_iterate_mcp
```

Or add the MCP server manually to Claude's config:

```json
{
  "mcpServers": {
    "brand-gen": {
      "command": "python3",
      "args": ["-m", "brand_gen.brand_iterate_mcp"],
      "cwd": "/absolute/path/to/brand-gen"
    }
  }
}
```

## Pi

The tracked Pi integration lives in [`packages/pi-brand-gen/`](../packages/pi-brand-gen/README.md).

### Install Pi

Follow the [Pi quickstart](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md):

```bash
npm install -g @mariozechner/pi-coding-agent
export ANTHROPIC_API_KEY=sk-ant-...
pi
```

### Build the extension

```bash
cd packages/pi-brand-gen
npm install
npm run typecheck
```

### Register and verify

Point Pi at the local extension directory, then:

```text
/brand-gen status
/brand-gen brands
/brand-gen summary
```

Config example:

```json
{
  "brandGenDir": "~/.brand-gen",
  "approvalMode": "output_only",
  "heartbeatIntervalMinutes": 60,
  "autoHeartbeat": true
}
```

`brandIterateMcpPath` is optional for a normal repo checkout. The extension auto-detects `<repo>/brand_gen/brand_iterate_mcp.py`. Only set it if your layout is unusual.

The extension prefers the repo-local venv when it exists:

```text
<repo>/.venv/bin/python <repo>/brand_gen/brand_iterate_mcp.py
```

### Pi commands

```text
/brand-gen brands           # list saved brands
/brand-gen switch <brand>   # activate a brand
/brand-gen generate x-feed Launch announcement
```

For the intended Pi subagent workflow, see the README's [Pi agent process spec](../README.md#pi-agent-process-spec). The short version: use `brand-orchestrator` as the entry point and keep the staged order `explorer -> router -> planner -> critic -> generator -> critic`.

Creating brands is CLI-first today: `bgen create-brand ...` or `bgen start-testing ...`.

## OpenClaw

The tracked OpenClaw integration lives in [`packages/openclaw-brand-gen/`](../packages/openclaw-brand-gen/README.md).

```bash
cd packages/openclaw-brand-gen
npm install
npm run typecheck
```

Then add the plugin to your OpenClaw config and point it at the brand-gen backend.

**Skills-only (no plugin):**

```yaml
skills:
  paths:
    - /path/to/brand-gen/skills/brand-gen-setup
    - /path/to/brand-gen/skills/brand-gen
    - /path/to/brand-gen/skills/brand-gen-orchestration
    - /path/to/brand-gen/skills/brand-gen-reference
```

## Environment and workspace notes

- The repo-local `.env` is the preferred configuration source.
- Set `BRAND_GEN_DIR` if you want durable state outside the repo checkout.
- Pi and OpenClaw integrations use their own `brandGenDir` plugin config, typically a shared root such as `~/.brand-gen`.

## Local configuration

Pi agents need a `.brand-gen-local.json` file at the repo root for machine-specific paths. This file is created automatically during setup.

```bash
cp .brand-gen-local.json.example .brand-gen-local.json
```

Fields:
- `repo_root` — absolute path to the brand-gen checkout (auto-detected)
- `vault_paths` — optional Obsidian vault or brand docs folders

This file is gitignored.
