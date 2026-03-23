# pi-brand-gen

Native Pi extension for brand-gen. It wraps the Python MCP backend, injects workspace context into Pi sessions, exposes host-native tools/commands, and shares runtime logic through `packages/brand-gen-core/`.

## Features

- brand-gen MCP bridge to the Python backend
- native Pi tools: `brand_search`, `brand_execute`, `brand_status`
- `/brand-gen` command surface
- widget/status panel support
- session lifecycle hooks and context prepend on `before_agent_start`
- heartbeat scheduling plus prompt-triggered heartbeat
- access to workspace summary, blackboard, iteration memory, capabilities, learnings, and recent journal entries
- derivative flows for mockups and video
- inspiration consolidation plus critique / feedback passthroughs

## Requirements

- a repo checkout of `brand-gen` (this package depends on local `../brand-gen-core`)
- Node.js + npm for the extension package
- Python 3 with access to brand-gen's MCP backend (`mcp/brand_iterate_mcp.py`)
- a Pi host that supports local extensions

## Quickstart

If you want Pi to be the default way you use brand-gen, do this:

### 0. Install Pi

Pi's official coding-agent quickstart is here:

- [badlogic/pi-mono `packages/coding-agent` README](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/README.md)

The current quickstart there is:

```bash
npm install -g @mariozechner/pi-coding-agent
```

Then either export an API key and start Pi:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pi
```

or start Pi and authenticate with `/login`:

```bash
pi
/login
```

### 1. Prepare the backend from the repo root

```bash
cd /absolute/path/to/brand-gen
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
cp .env.example .env
python3 scripts/validate_setup.py
```

Set `REPLICATE_API_TOKEN` in `.env`.

### 2. Build the Pi extension

```bash
cd packages/pi-brand-gen
npm install
npm run typecheck
```

### 3. Register the local extension in Pi

brand-gen's Pi integration currently ships from this repo checkout under `packages/pi-brand-gen/`; it is not yet a standalone published Pi package.

Register this package directory in Pi:

```text
/absolute/path/to/brand-gen/packages/pi-brand-gen
```

Use this config:

```json
{
  "brandIterateMcpPath": "/absolute/path/to/brand-gen/mcp/brand_iterate_mcp.py",
  "brandGenDir": "~/.brand-gen",
  "approvalMode": "output_only",
  "heartbeatIntervalMinutes": 60,
  "autoHeartbeat": true
}
```

### 4. Verify the extension inside Pi

Run:

```text
/brand-gen status
/brand-gen brands
/brand-gen summary
/brand-gen switch <brand>
/brand-gen generate x-feed Launch announcement
```

### Python runtime note

This extension launches the backend with:

```text
python3 /absolute/path/to/brand-gen/mcp/brand_iterate_mcp.py
```

So the `python3` visible to Pi must be able to import brand-gen's Python dependencies. The repo `.env` is still read by the backend automatically, but the interpreter itself must be correct. The safest path is to launch Pi from the same environment where you installed brand-gen or otherwise ensure that host `python3` has the required packages.

### Brand switching in Pi

You do **not** have to switch brands only through freeform conversation.

Use:

```text
/brand-gen brands
/brand-gen switch <brand>
```

The Pi extension exposes explicit switching for existing saved brands. The one current limitation is that the brand list is only available through `/brand-gen brands` or the `brand_search` tool surface — there is not a separate dedicated widget for it. Creating a new saved brand or starting a testing session is still CLI-first today (`bgen create-brand ...` / `bgen start-testing ...`), unless your Pi host also gives the agent separate shell access.

## Install from the repo checkout

```bash
cd packages/pi-brand-gen
npm install
npm run typecheck
```

Then use Pi's normal local-extension registration flow and point it at this package directory.

## Configuration

The Pi extension config schema is declared in `pi.extension.json`.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `brandGenDir` | `string` | no | host-specific / usually `~/.brand-gen` | Durable workspace root for brands, sessions, and runtime markers |
| `brandIterateMcpPath` | `string` | **yes** | — | Absolute path to `mcp/brand_iterate_mcp.py` |
| `approvalMode` | `"all" \| "output_only" \| "none"` | no | `"output_only"` | How much human approval is required between autonomous cycles |
| `logLevel` | `"debug" \| "info" \| "warn" \| "error"` | no | `"info"` | Extension log verbosity |
| `heartbeatIntervalMinutes` | `number` | no | `60` | Heartbeat timer interval |
| `autoHeartbeat` | `boolean` | no | `true` | Whether timer-based heartbeat runs automatically |

Example:

```json
{
  "brandGenDir": "~/.brand-gen",
  "brandIterateMcpPath": "/absolute/path/to/brand-gen/mcp/brand_iterate_mcp.py",
  "approvalMode": "output_only",
  "heartbeatIntervalMinutes": 60,
  "autoHeartbeat": true
}
```

Recommended quick-setup values:

- `brandIterateMcpPath` — always set this to the absolute repo path for `mcp/brand_iterate_mcp.py`
- `brandGenDir` — keep the default `~/.brand-gen` unless you want Pi to write state elsewhere
- `approvalMode` — `output_only` is the safest default for normal use
- `autoHeartbeat` — keep `true` unless you want Pi to stay entirely manual

## `/brand-gen` commands

- `/brand-gen status`
- `/brand-gen brands`
- `/brand-gen heartbeat`
- `/brand-gen switch <brand>`
- `/brand-gen summary`
- `/brand-gen reviews`
- `/brand-gen review <version>`
- `/brand-gen generate <materialType> <goal...>`
- `/brand-gen mockup <sourceVersion> [device-mockup|lifestyle-mockup|billboard-mockup]`
- `/brand-gen video <sourceVersion> [short-video|feature-animation|motion-loop]`
- `/brand-gen feedback <version> <score> [notes...]`
- `/brand-gen widget [show|hide]`

For a first smoke test, use:

1. `/brand-gen status`
2. `/brand-gen brands`
3. `/brand-gen summary`
4. `/brand-gen switch <brand>` if you need to change the active brand
5. `/brand-gen generate x-feed Launch announcement`

## `brand_search` actions

- `list_brands`
- `list_tools`
- `get_context`
- `get_session_summary`
- `get_blackboard`
- `get_iteration_memory`
- `get_workspace_status`
- `get_capabilities`
- `get_improvement_questions`
- `get_learnings`
- `get_recent_entries`
- `get_journal_stats`
- `get_pending_reviews`

## `brand_execute` actions

- `generate`
- `derive_mockup`
- `derive_video`
- `consolidate_inspiration`
- `submit_critique`
- `feedback`
- `switch_brand`
- `patch_learnings`
- `rate`

## Lifecycle / architecture

The extension does three main things:

1. starts the Python MCP backend on session start
2. prepends brand/workspace context before the agent begins working
3. optionally runs heartbeat discover/generate cycles during active sessions

It shares its workspace resolution, journal/learnings helpers, runtime-status markers, and heartbeat policy with OpenClaw through `packages/brand-gen-core/`.

## Development

```bash
npm install
npm run typecheck
npm test
```
