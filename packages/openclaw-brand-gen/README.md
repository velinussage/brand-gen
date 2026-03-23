# openclaw-brand-gen

OpenClaw plugin that bridges the brand-gen Python MCP runtime into an autonomous, memory-aware brand material generation agent. The plugin shares workspace, context, journal, and heartbeat logic with other host integrations through `packages/brand-gen-core/`.

## Requirements

- **Node.js >= 22.0.0** (uses `node:sqlite`)
- **Python 3** with access to brand-gen's MCP backend
- an OpenClaw-compatible host
- a repo checkout of `brand-gen` when developing/using the local package directly (the package depends on local `../brand-gen-core`)

## Install from the repo checkout

```bash
cd packages/openclaw-brand-gen
npm install
npm run typecheck
```

Then register the plugin with your OpenClaw host and point it at the repo-local brand-gen backend.

## Configuration

All settings go in the host's plugin config under the `openclaw-brand-gen` key.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `brandGenDir` | `string` | no | `~/.brand-gen` | Root directory for brands, sessions, config, runtime markers, and plugin memory |
| `brandIterateMcpPath` | `string` | **yes** | — | Absolute path to `mcp/brand_iterate_mcp.py` |
| `logoIterateMcpPath` | `string` | no | auto-derived | Optional path to `logo_iterate_mcp.py` |
| `approvalMode` | `"all" \| "output_only" \| "none"` | no | `"output_only"` | Controls human approval between autonomous cycles |
| `logLevel` | `"debug" \| "info" \| "warn" \| "error"` | no | `"info"` | Plugin log verbosity |
| `heartbeatIntervalMinutes` | `number` | no | `60` | Heartbeat timer interval |
| `autoHeartbeat` | `boolean` | no | `true` | Whether timer-based heartbeat runs automatically |

Example:

```json
{
  "openclaw-brand-gen": {
    "brandGenDir": "~/.brand-gen",
    "brandIterateMcpPath": "/home/user/brand-gen/mcp/brand_iterate_mcp.py",
    "approvalMode": "output_only",
    "heartbeatIntervalMinutes": 60,
    "autoHeartbeat": true
  }
}
```

## Registered tools

The plugin registers four tools with the host agent.

### `brand_search` (read-only)

Query plugin state without side effects.

| Action | Params | Returns |
|---|---|---|
| `list_tools` | — | Available MCP tools from the brand-gen backend |
| `get_learnings` | — | JSON learnings for the active workspace |
| `get_recent_entries` | `limit?: number` | Recent journal entries |
| `get_journal_stats` | — | Total, rated, average rating |
| `get_pending_reviews` | — | Outputs awaiting human rating |
| `get_context` | — | Full brand/workspace context |
| `get_session_summary` | — | Current workspace/session summary from brand-gen |
| `get_blackboard` | — | Active blackboard / learning summary |
| `get_iteration_memory` | — | Positive/negative examples and material notes |
| `get_workspace_status` | — | Canonical workspace root + alignment status |
| `get_capabilities` | — | Current material/model/tool capability surface |
| `get_improvement_questions` | — | Contextual questions to improve brand understanding |

### `brand_execute` (mutating)

Trigger brand-gen actions that modify state.

| Action | Params | Returns |
|---|---|---|
| `generate` | `materialType`, `goal`, `purpose`, `targetSurface` | Pipeline result with journal entry |
| `derive_mockup` | `sourceVersion`, `materialType?`, `prompt?`, `tag?` | Mockup derivative result |
| `derive_video` | `sourceVersion`, `materialType?`, `prompt?`, `tag?`, `duration?` | Video derivative result |
| `consolidate_inspiration` | `images` or `image`, `brandKey?`, `refresh?` | Saved inspiration-memory artifacts |
| `submit_critique` | `version`, `critique` | Stored structured critique result |
| `feedback` | `version`, `score`, `notes?`, `status?` | Stored version feedback result |
| `switch_brand` | `brand` | Switches active brand via backend |
| `patch_learnings` | `path`, `value` | Updates a JSON path in learnings |
| `rate` | `id`, `rating` (0-5), `feedback?` | Rates a journal output |

### `brand_status`

No parameters. Returns plugin health: bridge state, active brand/session, runtime root, pending reviews, journal stats, and heartbeat status.

### `logo_execute`

Passthrough to the logo iteration MCP server when configured. Whitelisted tools:

- `logo_generate`
- `logo_feedback`
- `logo_show`
- `logo_compare`
- `logo_evolve`
- `logo_bootstrap`
- `logo_inspire`

Usage: `{ tool: "logo_generate", params: { ... } }`

## Architecture

```text
OpenClaw host
  ├─ brand_search / brand_execute / brand_status / logo_execute
  ├─ openclaw-brand-gen plugin
  ├─ @brand-gen/core shared layer
  └─ MCP bridges
       ├─ brand_iterate_mcp.py
       └─ logo_iterate_mcp.py (optional)
```

Key internals:

- **McpBridge** — stdio JSON-RPC child-process bridge with recovery logic
- **Shared core** (`@brand-gen/core`) — workspace resolution, journal/learnings, context building, heartbeat policy, runtime-status markers
- **Heartbeat** — timed discover/generate cycles with approval safeguards and failure handling
- **Context injection** — `before_agent_start` prepends brand identity, blackboard, iteration memory, learnings, and recent journal entries

### `node:sqlite` note

This plugin uses Node's built-in `node:sqlite` module instead of an external SQLite dependency. Node 22+ may print an experimental warning on first use. That warning is expected.

## Development

```bash
npm install
npm run typecheck
npm test
```

## License

MIT
