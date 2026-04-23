# pi-brand-gen

Native Pi extension for brand-gen. It wraps the Python MCP backend, injects workspace context into Pi sessions, exposes host-native tools/commands, and shares runtime logic through `packages/brand-gen-core/`.

## Features

- brand-gen MCP bridge to the Python backend
- native Pi tools: 44 canonical `brand_*` verbs plus compatibility shims (`brand_search`, `brand_execute`, `brand_status`)
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
- Python 3 with access to brand-gen's MCP backend (`brand_gen/brand_iterate_mcp.py`)
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
  "brandGenDir": "~/.brand-gen",
  "approvalMode": "output_only",
  "heartbeatIntervalMinutes": 60,
  "autoHeartbeat": false
}
```

`brandIterateMcpPath` is optional for a normal repo checkout or fork. When Pi points at `packages/pi-brand-gen/`, the extension auto-detects `<repo>/brand_gen/brand_iterate_mcp.py`. Only set `brandIterateMcpPath` if your checkout layout is unusual or you want to override the backend path manually.

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

This extension launches the backend by preferring the repo-local Python environment when it exists:

```text
<repo>/.venv/bin/python <repo>/brand_gen/brand_iterate_mcp.py
```

If that repo-local Python interpreter is not present, it falls back to:

```text
python3 <repo>/brand_gen/brand_iterate_mcp.py
```

So a normal fork/checkout can work without any absolute MCP-path config as long as you keep the standard repo layout. The repo `.env` is still read by the backend automatically. The safest path is to create the repo `.venv`; otherwise ensure the host `python3` visible to Pi has brand-gen's Python dependencies.

### Brand switching in Pi

You do **not** have to switch brands only through freeform conversation.

Use:

```text
/brand-gen brands
/brand-gen switch <brand>
```

The Pi extension exposes explicit switching for existing saved brands. The brand list is available through `/brand-gen brands`, `brand_list_brands`, or the deprecated `brand_search` compatibility surface — there is not a separate dedicated widget for it. Creating a new saved brand or starting a testing session is still CLI-first today (`bgen create-brand ...` / `bgen start-testing ...`), unless your Pi host also gives the agent separate shell access.

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
| `brandIterateMcpPath` | `string` | no | auto-detected from the registered checkout | Optional override for the path to `brand_gen/brand_iterate_mcp.py` |
| `approvalMode` | `"all" \| "output_only" \| "none"` | no | `"output_only"` | How much human approval is required between autonomous cycles |
| `logLevel` | `"debug" \| "info" \| "warn" \| "error"` | no | `"info"` | Extension log verbosity |
| `heartbeatIntervalMinutes` | `number` | no | `60` | Heartbeat timer interval |
| `autoHeartbeat` | `boolean` | no | `false` | Whether timer-based heartbeat runs automatically. Off by default because it runs a full generation cycle, not a health check. |

Example:

```json
{
  "brandGenDir": "~/.brand-gen",
  "approvalMode": "output_only",
  "heartbeatIntervalMinutes": 60,
  "autoHeartbeat": false
}
```

Recommended quick-setup values:

- `brandIterateMcpPath` — leave unset for a normal fork/checkout; only override it if the extension cannot infer the backend path from the repo layout
- `brandGenDir` — keep the default `~/.brand-gen` unless you want Pi to write state elsewhere
- `approvalMode` — `output_only` is the safest default for normal use
- `autoHeartbeat` — keep `false` unless you explicitly want autonomous background generation

## `/brand-gen` commands

- `/brand-gen status`
- `/brand-gen brands`
- `/brand-gen heartbeat`
- `/brand-gen switch <brand>`
- `/brand-gen summary`
- `/brand-gen reviews`
- `/brand-gen review <version>`
- `/brand-gen generate <materialType> <goal...>`
- `/brand-gen mockup <sourceVersion> [device-mockup|lifestyle-mockup|website-hero-illustration]`
- `/brand-gen video <sourceVersion> [short-video|feature-animation|motion-loop]`
- `/brand-gen feedback <version> <score> [notes...]`
- `/brand-gen widget [show|hide]`

For a first smoke test, use:

1. `/brand-gen status`
2. `/brand-gen brands`
3. `/brand-gen summary`
4. `/brand-gen switch <brand>` if you need to change the active brand
5. `/brand-gen generate x-feed Launch announcement`

## Deprecated `brand_search` compatibility actions

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

## Deprecated `brand_execute` compatibility actions

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
