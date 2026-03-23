# Architecture

## High-level flow

Standard generative flow:

```text
route-request → plan-draft → critique-plan → build-generation-scratchpad → generate
```

Convenience surface:

```text
pipeline = route-request → plan-draft → critique-plan → build-generation-scratchpad → generate
```

Review / learning flow:

```text
critique-rubric → agent/human review → submit-critique → feedback → compare / evolve
```

Set flow:

```text
plan-set → validate-brand-fit / validate-set → generate-set
```

## Runtime layers

1. **Python runtime (`mcp/`)**
   - command registry, CLI builders, and package entrypoints
   - planning, critique, generation, and review logic
   - share-card HTML renderer and card-data plugins
   - workspace/state resolution and file IO helpers

2. **Durable workspace (`.brand-gen/`)**
   - saved brands under `brands/<brand>/`
   - testing sessions under `sessions/<session>/brand-materials/`
   - active selectors in `config.json`
   - runtime markers under `runtime-status/plugins/`

3. **Shared host core (`packages/brand-gen-core/`)**
   - workspace resolution for plugins
   - journal + learnings persistence
   - context building and prepend summaries
   - heartbeat cycles and runtime status snapshots

4. **Host adapters (`packages/pi-brand-gen/`, `packages/openclaw-brand-gen/`)**
   - native host tools/commands
   - host lifecycle hooks
   - MCP bridge startup/shutdown

## Workspace resolution

The runtime resolves the active workspace in this order:

1. `BRAND_GEN_DIR` when explicitly set
2. repo-local `.brand-gen/` when present for CLI/direct runtime use
3. active session from `.brand-gen/config.json`
4. active saved brand from `.brand-gen/config.json`
5. legacy `BRAND_DIR` / `LOGO_DIR` / `SCREENSHOTS_DIR` fallbacks when needed

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

The command surface is defined once in `mcp/command_registry.py` and exposed through two front doors:

- CLI parser + builders from `mcp/cli_builders.py`
- MCP tool schemas generated from the registry via `mcp/mcp_bridge_registry.py`

Most MCP tools are automatic `brand_<command>` bridges. Two tools remain intentionally custom:

- `brand_pipeline`
- `brand_inspire`

This keeps the CLI and MCP surfaces aligned while still allowing a few high-level convenience tools.

## Critique semantics

- `critique-plan` is advisory/reporting-first unless you explicitly choose strict behavior
- `build-generation-scratchpad` and `pipeline` are strict by default
- `allow_blocking` records an explicit bypass when generation continues past blocking critique findings
- automatic `*-auto-review.md` artifacts are deterministic QA outputs, not visual-review guarantees
- the default visual review path is `critique-rubric` → `submit-critique`
- the legacy internal VLM critique loop is explicit opt-in only

## Blackboard, run ledger, and plugin journal

The runtime uses multiple memory surfaces with different jobs:

- **Blackboard** — active brief, decisions, reference assignments, latest artifact pointers
- **Run ledger** — append-only operational trace under `runs/<workflow_id>.jsonl`
- **Iteration memory** — positive/negative examples and material-specific notes
- **Plugin journal** — host-layer execution history, now preferring `runs/journal.jsonl` with legacy `brand.sqlite` compatibility when older data exists
- **Learnings JSON** — plugin-layer distilled learnings in `learnings.json`

## Branching and lineage

Every pipeline run is implicitly a branch. The `branch_id` defaults to the `workflow_id`.

Important lineage fields:

- `source_version` — version being iterated from
- `branch_id` — current branch identifier
- `parent_branch_id` — source branch identifier
- `selected_direction_id` — inspiration direction chosen for the run

These show up in manifests, blackboard state, scratchpads, and run logs.

## Route override telemetry

Explicit route overrides record both what the runtime recommended and what actually ran.

- `recommended_route`
- `chosen_route`
- `override_reason`
- `override_actor`

This is surfaced in `show-workflow-lineage` and counted in session summaries.

## Share-card path

Share cards are now HTML-rendered, not Stitch-rendered.

The path is:

```text
source_url → card-data plugin → structured payload → HTML layout → Chrome PNG render
```

Built-ins currently include:

- specialized **Sage** plugin
- generic **Web** fallback plugin

Additional platforms can be added through `mcp/card_plugins/`.

## Host runtime markers

Native host plugins write status markers to:

- `.brand-gen/runtime-status/plugins/pi-brand-gen.json`
- `.brand-gen/runtime-status/plugins/openclaw-brand-gen.json`

These markers help the CLI/runtime report workspace alignment, active brand/session, and plugin health.

## Key commands

- `pipeline` — default one-call generative flow
- `show-session-summary` — fastest “what changed?” surface
- `context-snapshot` — canonical machine-readable workspace context
- `workspace-status` — current root + alignment warnings
- `review-brand` / `critique-rubric` / `submit-critique` — modern review path
- `plan-set` / `validate-set` / `generate-set` — coordinated multi-material workflows
