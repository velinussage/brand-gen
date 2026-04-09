# Architecture

## System overview

```
┌─────────────────────────────────────────────────────────┐
│                     Your AI Agent                       │
│  (Claude Code / Pi / OpenClaw / Codex / Cursor / ...)   │
└───────────┬──────────────────────┬──────────────────────┘
            │ CLI                   │ MCP (stdio)
            ▼                      ▼
┌───────────────────────────────────────────────────────┐
│                  brand_gen/  (Python)                  │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ cli.py   │  │ mcp      │  │ command_registry  │    │
│  │ (bgen)   │  │ bridge   │  │ (single source)   │    │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘    │
│       │              │                 │              │
│       └──────────────┴─────────────────┘              │
│                      │                                │
│  ┌───────────────────┼───────────────────────────┐    │
│  │           Pipeline Engine                     │    │
│  │                                               │    │
│  │  route_predicates → plan_builder →            │    │
│  │  plan_validation → pipeline_runner →           │    │
│  │  prompt_assembly → generate                   │    │
│  └───────────────────────────────────────────────┘    │
│                      │                                │
│  ┌───────────────────┼───────────────────────────┐    │
│  │         Workspace / State Layer               │    │
│  │                                               │    │
│  │  runtime_brand  runtime_paths  session         │    │
│  │  blackboard     run_ledger     iteration_memory│    │
│  └───────────────────────────────────────────────┘    │
│                      │                                │
│  ┌───────────────────┼───────────────────────────┐    │
│  │         Review / Learning Layer               │    │
│  │                                               │    │
│  │  critique_policy  agent_review  vlm_critique   │    │
│  │  inspiration_memory  learnings_memory          │    │
│  └───────────────────────────────────────────────┘    │
│                      │                                │
│  ┌───────────────────┼───────────────────────────┐    │
│  │         Share Cards / Media                   │    │
│  │                                               │    │
│  │  card_engine  card_builder  card_plugins/      │    │
│  │  media_board  share_card_renderer              │    │
│  └───────────────────────────────────────────────┘    │
└───────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────────┐
│              .brand-gen/  (Durable State)              │
│                                                       │
│  brands/<brand>/          sessions/<session>/          │
│    brand-profile.json       brand-materials/           │
│    brand-identity.json        manifest.json            │
│    blackboard.json            blackboard.json          │
│    learnings.json             iteration-memory.json    │
│                               runs/                    │
│                               reviews/                 │
│  config.json                  scratchpads/             │
│  runtime-status/plugins/                               │
└───────────────────────────────────────────────────────┘
```

## Pipeline flow

### Generation

```
route-request → plan-draft → critique-plan → build-generation-scratchpad → generate
```

The `pipeline` command runs this full sequence in one call.

### Review / learning

```
critique-rubric → agent/human review → submit-critique → feedback → compare / evolve
```

### Set generation

```
plan-set → validate-brand-fit / validate-set → generate-set
```

## Runtime layers

1. **Python runtime (`brand_gen/`)**
   - Command registry, CLI builders, and package entrypoints
   - Planning, critique, generation, and review logic
   - Share-card HTML renderer and card-data plugins
   - Workspace/state resolution and file IO helpers

2. **Durable workspace (`.brand-gen/`)**
   - Saved brands under `brands/<brand>/`
   - Testing sessions under `sessions/<session>/brand-materials/`
   - Active selectors in `config.json`
   - Runtime markers under `runtime-status/plugins/`

3. **Shared host core (`packages/brand-gen-core/`)**
   - Workspace resolution for plugins
   - Journal + learnings persistence
   - Context building and prepend summaries
   - Heartbeat cycles and runtime status snapshots

4. **Host adapters (`packages/pi-brand-gen/`, `packages/openclaw-brand-gen/`)**
   - Native host tools/commands
   - Host lifecycle hooks
   - MCP bridge startup/shutdown

## Workspace resolution

The runtime resolves the active workspace in this order:

1. `BRAND_GEN_DIR` when explicitly set
2. Repo-local `.brand-gen/` when present for CLI/direct runtime use
3. Active session from `.brand-gen/config.json`
4. Active saved brand from `.brand-gen/config.json`
5. Legacy `BRAND_DIR` / `LOGO_DIR` / `SCREENSHOTS_DIR` fallbacks

Pi and OpenClaw keep their own `brandGenDir` plugin config and generally point to a shared root outside the repo checkout.

## State model

### Saved brand memory

Durable saved-brand state lives under:

- `.brand-gen/brands/<brand>/brand-profile.json`
- `.brand-gen/brands/<brand>/brand-identity.json`
- `.brand-gen/brands/<brand>/blackboard.json`
- `.brand-gen/brands/<brand>/learnings.json` (plugin layer)

### Session workspace

Testing sessions live under:

- `.brand-gen/sessions/<session>/brand-materials/manifest.json`
- `.brand-gen/sessions/<session>/brand-materials/blackboard.json`
- `.brand-gen/sessions/<session>/brand-materials/iteration-memory.json`
- `.brand-gen/sessions/<session>/brand-materials/runs/`
- `.brand-gen/sessions/<session>/brand-materials/reviews/`
- `.brand-gen/sessions/<session>/brand-materials/scratchpads/`
- `.brand-gen/sessions/<session>/brand-materials/learnings.json` (plugin layer)

### Prompt artifacts

- `resolved_prompt` = fuller inspection/debug prompt with richer context
- `execution_prompt` = the actual model-call prompt used for generation
- `effective_prompt` = backward-compatibility alias for older consumers

## Command registry and MCP bridge

The command surface is defined once in `brand_gen/command_registry.py` and exposed through two front doors:

- CLI parser + builders from `brand_gen/cli_builders.py`
- MCP tool schemas generated from the registry via `brand_gen/mcp_bridge_registry.py`

Most MCP tools are automatic `brand_<command>` bridges. Two tools remain intentionally custom:

- `brand_pipeline`
- `brand_inspire`

This keeps the CLI and MCP surfaces aligned while still allowing a few high-level convenience tools.

## Critique semantics

- `critique-plan` is advisory/reporting-first unless you explicitly choose strict behavior
- `build-generation-scratchpad` and `pipeline` are strict by default
- `allow_blocking` records an explicit bypass when generation continues past blocking critique findings
- Automatic `*-auto-review.md` artifacts are deterministic QA outputs, not visual-review guarantees
- The default visual review path is `critique-rubric` → `submit-critique`
- The legacy internal VLM critique loop is explicit opt-in only

## Memory surfaces

| Surface | Job |
|---------|-----|
| **Blackboard** | Active brief, decisions, reference assignments, latest artifact pointers |
| **Run ledger** | Append-only operational trace under `runs/<workflow_id>.jsonl` |
| **Iteration memory** | Positive/negative examples and material-specific notes |
| **Plugin journal** | Host-layer execution history in `runs/journal.jsonl` |
| **Learnings JSON** | Plugin-layer distilled learnings in `learnings.json` |

## Branching and lineage

Every pipeline run is implicitly a branch. The `branch_id` defaults to the `workflow_id`.

Important lineage fields:

- `source_version` — version being iterated from
- `branch_id` — current branch identifier
- `parent_branch_id` — source branch identifier
- `selected_direction_id` — inspiration direction chosen for the run

These show up in manifests, blackboard state, scratchpads, and run logs.

## Share-card path

```
source_url → card-data plugin → structured payload → HTML layout → Chrome PNG render
```

Built-in plugins: platform-specific (ships with Sage Protocol example) and generic **Web** fallback. Additional platforms can be added through `brand_gen/card_plugins/`.

## Key commands

| Command | Purpose |
|---------|---------|
| `pipeline` | Default one-call generative flow |
| `show-session-summary` | Fastest "what changed?" surface |
| `context-snapshot` | Canonical machine-readable workspace context |
| `workspace-status` | Current root + alignment warnings |
| `review-brand` / `critique-rubric` / `submit-critique` | Modern review path |
| `plan-set` / `validate-set` / `generate-set` | Coordinated multi-material workflows |
