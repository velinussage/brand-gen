# Host setup — typed runtime across Claude Code, Pi, and OpenClaw

Phase 5 of the typed-agentic-runtime refactor consolidated all three hosts (Claude Code subagents, Pi plugin, OpenClaw plugin) onto the same ≤25-verb typed tool surface. This doc is the architecture reference.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Hosts (thin adapters, ≤150 LoC each)                           │
│                                                                 │
│  Claude Code subagent  │  Pi plugin        │  OpenClaw plugin   │
│  (.claude/agents/*.md) │  (pi-brand-gen)   │  (openclaw-*)      │
│                                                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │ same 25 typed tools
┌──────────────────────┴──────────────────────────────────────────┐
│                                                                 │
│  Canonical tool registry                                        │
│    packages/brand-gen-core/src/tool-registry.ts                 │
│    → CANONICAL_TOOLS (25 entries: 7 orchestration, 9 mutation,  │
│      7 inspection, 2 feedback)                                  │
│                                                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │ callJsonTool dispatch via MCP stdio
┌──────────────────────┴──────────────────────────────────────────┐
│                                                                 │
│  Python MCP bridge (brand_gen/)                                 │
│    brand_gen/mcp_bridge_registry.py                             │
│    → BRIDGE_BY_TOOL (same 25 tool_names + schemas)              │
│                                                                 │
│  Per-agent allowlist                                            │
│    brand_gen/agent_specialization.py                            │
│    → 9 agents × canonical-tool subsets                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

All three hosts expose the same tool names. The Python bridge is the single execution path. The typed tool schema is the contract.

## What each host does

- **Claude Code subagent**: an `.md` file in `.claude/agents/` with `tools: [...]` frontmatter listing the agent's canonical allowlist. The agent calls tools; it does not run bash sequences. Claude Code auto-registers the MCP server declared in `.mcp.json` (or the session config).
- **Pi plugin** (`packages/pi-brand-gen`): at plugin startup, `createCanonicalBrandTools(bridge, config)` registers all 25 canonical tools plus three compatibility shims (`brand_search`, `brand_execute`, `brand_status`). Context injection and heartbeat logic live in `packages/brand-gen-core`.
- **OpenClaw plugin** (`packages/openclaw-brand-gen`): same canonical registration pattern; OpenClaw's tool execute signature is `(toolCallId, params) → result` vs Pi's `(args) → result`, so there's a small adapter but the tool name + schema identical.

## Setting up a new host (≤100 lines of adapter code)

Any agent host with shell access can plug in. The adapter must:

1. Spawn the brand-gen MCP server: `python -m brand_gen.brand_iterate_mcp` (stdio transport).
2. Call `generateHostTools(bridge, config)` from `packages/brand-gen-core/src/tool-registry.ts` at startup.
3. Register each returned `HostToolDefinition` with the host's native tool-registration API.
4. (Optional) Call `buildBrandGenContext(bridge, config)` to prepend workspace context to every agent prompt.
5. (Optional) Schedule `runHeartbeatCycle` on the interval the host supports.

That's the whole contract. No business logic in the adapter.

## Claude Code agent markdown contract

Every `.claude/agents/brand-*.md` file:

- Has a `tools:` frontmatter field listing only canonical tool names from `brand_gen/agent_specialization.py::AGENT_SPECIALIZATIONS`.
- Describes the agent's specialization + stop-reason handling in ≤80 lines.
- Does **not** contain procedural `bgen` bash sequences. The tool surface IS the contract.
- Does **not** instruct the agent to edit JSON or markdown files directly. Every mutation goes through a typed tool.

Mirrors live at `.pi/agents/` (Pi-flavored frontmatter: `model: "gpt-5.3-codex"`) and `skills/brand-gen/claude-agents/` (distribution mirror). The orchestrator markdown is byte-equivalent across the `.claude/` and `skills/` mirrors; the Pi mirror differs only in frontmatter.

## Per-agent tool allowlists

Declared once in `brand_gen/agent_specialization.py`:

| Agent | Tools granted |
|---|---|
| `brand-orchestrator` | Full 7 orchestration + inspection + critic mutations |
| `brand-explorer` | 7 inspection verbs (read-only) |
| `brand-router` | 7 inspection verbs (read-only) |
| `brand-planner` | `brand_plan_run`, `brand_validate_run`, 7 inspection verbs |
| `brand-critic` | `brand_validate_run`, `brand_review_run`, 7 inspection verbs, 5 critic mutations |
| `brand-generator` | `brand_execute_run`, 4 inspection verbs |
| `brand-philosopher` | 5 philosopher mutations + 7 inspection verbs |
| `brand-cinematographer` | `brand_execute_run`, `brand_set_motion_grammar`, 4 inspection verbs |
| `brand-interviewer` | 4 interview mutations + `brand_capabilities` |

Adding a new tool to an agent: edit `AGENT_SPECIALIZATIONS` in `agent_specialization.py`, re-sync the three markdown mirrors, and run `tests/test_host_consistency.py`.

## Adding a new tool to the canonical surface

1. Add the CLI command in `brand_gen/commands/` with a typed response.
2. Register the bridge in `brand_gen/mcp_bridge_registry.py`.
3. Append to `CANONICAL_TOOLS` in `packages/brand-gen-core/src/tool-registry.ts`.
4. If specific agents need it, add to their `canonical_tools` tuple in `agent_specialization.py`.
5. Run `tests/test_mcp_schema_parity.py` + `tests/test_host_consistency.py` — both must pass.

That's the whole surface-extension procedure. No per-host code changes needed.

## Testing

- `tests/test_mcp_schema_parity.py` — asserts TS canonical list ↔ Python bridges are in sync.
- `tests/test_host_consistency.py` — asserts every agent specialization's tools are in the canonical list, every agent has a markdown file in all three mirrors, and the orchestrator contract is byte-equivalent between `.claude/agents/` and `skills/brand-gen/claude-agents/` (the Pi mirror differs only in frontmatter).

## Rollback path

If a new tool misbehaves on one host but not others, the blast radius is the tool's own CLI handler in `brand_gen/commands/` — the host adapters pass arguments verbatim. Revert the CLI change; all three hosts recover simultaneously.

## Legacy bash-based usage

Any agent with shell access can still fall back to raw `bgen` commands (the 82-command CLI surface remains available). Example:

```text
Read skills/brand-gen/SKILL.md and follow it for brand material work.
Start by running: source .venv/bin/activate && bgen context-snapshot --format json
```

This works with older agent setups or when the MCP server can't be started. However, the preferred path for any new integration is the typed tool surface above — agents are more reliable when they navigate capabilities instead of scripting shell sequences.

## MCP server

For hosts that want a direct tool surface over stdio:

```bash
python3 -m brand_gen.brand_iterate_mcp
```

Exposes all 82 bridged commands (for backward compatibility) plus the 25 canonical verbs as native MCP tools.
