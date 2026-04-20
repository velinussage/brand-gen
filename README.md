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
- **Custom scratchpad**: persistent per-brand `custom-scratchpad.md` + `.json` auto-injected into prompts; agents write style directives and forbidden patterns directly
- **Design tokens + WCAG audit**: `bgen export-design-tokens` emits CSS / Tailwind / JSON / W3C DTCG with hard-gate AA contrast checking
- **Seedance video pipeline**: `brand-cinematographer` agent + `seedance-2-pro` model + seven-rule shot-design validator + `launch_producer.py` for multi-shot launch films

## Custom scratchpad

Every brand workspace can carry a persistent, agent-editable scratchpad that gets auto-injected into every prompt and auto-applied to model selection.

```
.brand-gen/brands/<brand>/
├── custom-scratchpad.md     # agent-authored style directives, motion grammar, bans
└── custom-scratchpad.json   # {model_overrides_by_material, forbidden_patterns[]}
```

- `brand-philosopher` writes style directives and motion grammar directly
- `brand-critic` appends forbidden patterns after any P1 finding
- `brand-orchestrator` reads both files in Phase 1 and applies model overrides before learnings lookup

The scratchpad contents land in `build_effective_prompt` alongside iteration memory and blackboard learnings, and model overrides fire before `resolve_default_model` runs.

## Design tokens

Brand-gen can emit production-ready design tokens derived mathematically from `brand-identity.json`. Every emit runs a WCAG AA audit before writing.

```bash
bgen export-design-tokens --output-format css       --format json   # CSS custom properties (default)
bgen export-design-tokens --output-format tailwind  --format json   # Tailwind theme
bgen export-design-tokens --output-format json      --format json   # flat JSON
bgen export-design-tokens --output-format w3c       --format json   # W3C DTCG
```

The JSON response includes a `.wcag` block with the full audit. WCAG errors block emission unless `--skip-audit` is passed — palettes that fail AA contrast don't ship by default. Output lands at `.brand-gen/brands/<active>/design-tokens/`.

Output covers the full token ecosystem: 50–950 shade scales per base color, math-derived type scale with line-height and letter-spacing rules, base-4 spacing grid, elevation shadows keyed to the brand's neutral, radii, motion tokens, breakpoints, and smart font-family fallback chains.

See `skills/brand-gen/references/design-tokens.md` for the full algorithms and schemas (distilled from dylanfeltus/design-tokens, pbc-os/brand-identity, and anthropics/brand-guidelines).

## Video materials

For any video material (`short-video`, `derive-video`, `motion-card`, `launch-film`, `announcement-video`, `brand-bumper`), use the `brand-cinematographer` agent.

It reads the motion grammar that `brand-philosopher` writes into `custom-scratchpad.md` from `skills/brand-gen/references/seedance-shot-design.md`:

- director tokens (the safe-phrasing paragraphs from §2 — monumental-compression, available-light restraint, digital-sky-gradient, etc.)
- cinematography dictionary (§3) with 50+ safe camera-move phrases
- three-layer lighting recipe (§4) — source + behavior + grade
- film-stock + organic-imperfection anchors (§5) that kill the "plastic AI look"
- seven-rule validation (§8) — length, time slices, camera literacy, filler bans, asset caps, conflict scan, bare-word scrub

The `seedance-2-pro` model is registered in `brand_gen/models.json`. The `launch_producer.py` module (invoked via `bgen create-video`) runs a brief-driven multi-shot pipeline with xfade stitching and per-shot validation via `brand_gen/seedance_validation.py`. Every shot is gated by the seven-rule checklist before generation fires.

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

## Pi agent process spec

When brand-gen is used through Pi subagents, the intended entry point is **`brand-orchestrator`**. Do not jump straight to `bgen generate` or treat `bgen pipeline` as a freehand shortcut. The Pi layer is a supervisory workflow around the Python runtime.

### Default entry point

```text
/run brand-orchestrator <task>
```

### Specialist agents

- `brand-orchestrator` — coordinates the full workflow; in Phase 1 runs `export-design-tokens` and delegates WCAG failures to the philosopher
- `brand-explorer` — reads workspace state, blackboard, learnings, recent versions
- `brand-router` — chooses the correct route before planning
- `brand-planner` — creates the plan draft with learnings, layout, and role-pack context
- `brand-critic` — blocks bad plans, scores outputs, runs WCAG contrast audits on HTML share cards, and appends forbidden patterns directly into `custom-scratchpad.json`
- `brand-generator` — builds the scratchpad and runs generation from an approved plan; prefers the brand's `design-tokens.css` when rendering HTML
- `brand-philosopher` — creates or refines `design-philosophy.md`, curates `custom-scratchpad.md` (style directives + motion grammar), and fixes WCAG failures by adjusting `brand-identity.json`
- `brand-cinematographer` — video-prompt specialist; reads motion grammar and the seedance shot-design reference, assembles the six-element prompt, runs seven-rule validation before handoff to `brand-generator`

### Mandatory generation sequence

For any real generation request, the intended order is:

1. **Explorer** — inspect workspace, blackboard, learnings, prior winners, references
2. **Router** — choose the route (`reference_translate`, `generative_explore`, etc.)
3. **Planner** — run preparation and produce `plan-draft`
4. **Critic** — run `critique-plan` and `validate-brand-fit`; block if invalid
5. **Generator** — run `build-generation-scratchpad` and `generate` only after approval
6. **Critic again** — run `critique-rubric`, score the output, and decide approve vs iterate
7. **Orchestrator** — record `feedback`, run `evolve`, and summarize the run

If steps 1-4 are skipped, the workflow is invalid. No freehand generation before the plan is critiqued.

### How the Pi agents map to `bgen`

The subagents wrap the normal command surface rather than replacing it:

- `brand-explorer` → `context-snapshot`, `show-blackboard`, `show`, `capabilities`
- `brand-router` → route selection from workspace state and router rules
- `brand-planner` → `suggest-role-pack`, `suggest-layout`, `plan-draft`
- `brand-critic` → `critique-plan`, `validate-brand-fit`, then `critique-rubric`, `submit-critique`, `feedback`; WCAG audit via `export-design-tokens`
- `brand-generator` → `build-generation-scratchpad`, `generate` (consumes `design-tokens.css` for HTML renders)
- `brand-philosopher` → direct edits to `design-philosophy.md`, `custom-scratchpad.md`, and (indirectly) `brand-identity.json` after WCAG failures
- `brand-cinematographer` → `build-generation-scratchpad` for video materials using seedance shot-design discipline
- `brand-orchestrator` → enforces the order, runs `export-design-tokens` in Phase 1, and runs `evolve` at the end

So the real flow is:

```text
Pi subagents → inspect → route → plan → validate → generate → critique → evolve
                    ↓
                 bgen commands execute each stage
```

### Manual chain rule

If your host cannot run the Pi chain automatically, emulate the same order manually:

```text
brand-explorer -> brand-router -> brand-planner -> brand-critic -> brand-generator -> brand-critic
```

Include `brand-router` in the chain. It is part of the intended process, not an optional extra.

For video materials, insert `brand-cinematographer` between planner and generator:

```text
brand-explorer -> brand-router -> brand-planner -> brand-critic -> brand-cinematographer -> brand-generator -> brand-critic
```

If the brand has no `## Motion grammar` section in its `custom-scratchpad.md`, the cinematographer will stop and delegate back to `brand-philosopher` to establish one before any video generates.

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
