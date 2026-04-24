---
name: brand-gen
description: >
  Main skill for brand-gen — the file-backed brand-material runtime. Use for almost every
  brand-material session: onboarding into the correct workspace, choosing saved-brand vs testing
  session flows, planning assets or sets, running the pipeline, reviewing outputs, scoring,
  iterating, messaging ideation, inspiration capture, design-memory extraction, and deterministic
  HTML share cards. Prefer this skill whenever the user wants to create, inspect, critique,
  compare, or evolve branded materials through bgen or MCP tools.
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Gen

## Pi / Sage full-pipeline prompt

For Sage brand work in Pi, use the paste-ready prompt at `docs/prompts/pi-sage-brand-gen-full-pipeline.md`. It routes Pi through the typed `brand_*` tools, the `brand-orchestrator` subagent, exact-text gates, v2/DSPy review, GEPA-ready disagreement fields, and typed mutation loops. Keep this link instead of copying the full prompt into skill bodies.

For any non-Sage saved brand or testing session, use the generated brand-scoped
prompt at `<brand-dir>/prompts/pi-full-pipeline.md`. `bgen create-brand` and
`bgen start-testing` scaffold this prompt from the brand profile, approved copy,
and source-knowledge config so Sage-specific wording does not leak into new
brands.

brand-gen is a **multi-agent system**. The intended entry point for any brand material work is the `brand-orchestrator` agent, which walks a planning-first pipeline through six phases with quality gates. `bgen pipeline` exists as a scripting/CI fallback; it skips the philosopher's WCAG gate, the inspiration-readiness preflight, the cinematographer's shot validation, and the critic's P1 pushback. Prefer the orchestrator path unless you know exactly what you're bypassing.

## Typed runtime (2026-04+, preferred surface)

After the typed-agentic-runtime refactor, brand-gen exposes a **45-verb canonical tool surface** that every host (Claude Code, Pi, OpenClaw) calls through MCP. Pin to these verbs — they're shorter, discoverable without this skill file, and validated against the Python MCP bridge in `tests/test_mcp_schema_parity.py`.

Architecture docs for the typed runtime live in the repo-local `docs/architecture/` folder. Start with `docs/architecture/runtime-agent-contract.md`; use `docs/architecture/gepa-dspy-optimization.md` for GEPA/DSPy reflection records and optimizer targets.

### Orchestration (8 verbs)

One-shot convenience + six per-stage tools + scratchpad assembly. Each returns a typed response with `{run_id, next_action, artifacts}`.

```bash
bgen orchestrate-material --material-type concept-illustration --mode hybrid --source-version v018 --format json
# Returns {stages_completed, stop_reason, next_action, artifacts}.
# stop_reason ∈ {approved, blocking_findings, iterating, max_retries, needs_user_input}

# Per-stage fall-through for exception handling:
bgen prepare-run   # → {brand_dna_summary, applicable_learnings, readiness_issues}
bgen plan-run      # → {plan_id, plan_summary}
bgen validate-run  # → {status, blocking_issues, warnings, critique_id}
bgen execute-run   # → {version_id, image_paths, scratchpad_path}
bgen review-run    # → {axis_scores, decision, before_after_diffs}
bgen evolve-run    # → {learnings_promoted, improvement_questions, recommendation}
```

Each response's `next_action` is a direct hint to the tool to call next. Follow it unless you're A/B-testing a stage.

### Mutation (13 typed verbs — replace all direct file edits)

**Never manually edit `custom-scratchpad.json`, `custom-scratchpad.md`, `learnings.json`, `iteration-memory.json`, or `brand-identity.json`.** Call the typed verb instead. Every mutation tool supports `--dry-run` returning the same response shape, so you can preview before committing.

```bash
# Forbidden patterns / scratchpad notes (formerly: edit custom-scratchpad.json)
bgen append-forbidden-pattern --pattern "floating gradient orbs" --reason "Generic premium-AI slop" --dry-run --format json
bgen append-custom-scratchpad-note --section composition --text "No icon-worship centerpieces." --format json

# Learnings promotion (formerly: edit learnings.json)
bgen promote-learning --bucket modelPreferences --material-type concept-illustration --text "..." --format json
bgen promote-style-policy --material-type concept-illustration --reference-policy rotating_anchor_set \
  --anchor v012 --anchor v021 --anchor v088 --anchor v156 --anchor v018 --format json

# Identity mutations (formerly: edit brand-identity.json)
bgen update-palette --role primary --hex "#1A6B6B" --format json
bgen update-typography --role display --family "Inter" --fallback "sans-serif" --format json
bgen update-devices --add "doric-column-mark" --format json

# Motion grammar (formerly: free-write a section in custom-scratchpad.md)
bgen set-motion-grammar --director "..." --favored "..." --banned "..." --intensity medium --format json

# Review submission (alias for submit-critique)
bgen submit-review <version-id> --critique-json <path> --format json
```

### Inspection / policy-read (18 read verbs)

```bash
bgen context-snapshot --format json       # canonical workspace snapshot — run at every session start
bgen source-knowledge --query "..." --format json  # brand-scoped Obsidian/docs excerpts
bgen show-blackboard --format json        # active brief + decisions
bgen show-iteration-memory --format json  # positive/negative examples + rotation state
bgen show-rubric --material-type <type> --format json  # scoring contract before planning/critiquing
bgen show-disagreements --format json     # agent-vs-user score disagreements (calibration)
bgen scoring-status --format json         # weighted Cohen's kappa + agreement rate
bgen capabilities --format json           # available tools + material types
```

### v2 review decision rule (thresholds)

When `critique-rubric --dspy-scorer` (or `review-run`) returns a packet with `rubric_version` present:

1. If `disqualifier_triggered == true` → **REJECT** (overall_score is 1; bypass axis arithmetic).
2. If `overall_score < 3` → **ITERATE**.
3. If `overall_score >= 3` AND `disqualifier_triggered == false` → **APPROVE**.

`overall_score` is min-biased: any axis <2 caps overall at ≤2. `before_after_diffs` on the review packet is the honest fix list — each `{principle, before, after}` row feeds into the next iteration. You have two ways to apply those rows:

- **Durable (preferred)** — record them as typed mutations with `bgen append-forbidden-pattern` (for `before` clauses) and `bgen append-custom-scratchpad-note --section composition` (for `after` clauses). These persist across runs and drive the auto-ban pipeline.
- **Ephemeral (one-run override)** — pass `--ban "<before-clause>"` and `--push "<after-clause>"` inline on the next `bgen orchestrate-material` (or legacy `bgen pipeline`) call. These apply to a single run and do not persist.

Use durable when the `before` is a recurring slop pattern. Use ephemeral when the `before` is run-specific.

When `rubric_version` is absent → legacy v1 packet; score 4 axes manually and compute the mean.

### Rule: typed verb before file edit

Every time this skill or an agent instructs "edit this JSON file" or "append to this markdown section", stop. Pick the typed verb from the mutation list above. If no typed verb exists for the mutation you need, the skill is out of date — file that gap instead of hand-editing. Direct file edits bypass the run ledger, skip deprecation warnings, and corrupt agent-vs-user disagreement capture.

### When to use the legacy CLI chain below

The 100+ command CLI surface (`route-request`, `plan-draft`, `critique-plan`, `build-generation-scratchpad`, `generate`, `submit-critique`, `feedback`, `evolve`, `pipeline`, etc.) remains supported for:
- CI/scripting that needs a single blocking `bgen pipeline` call
- Debugging individual stages when `orchestrate-material` stops with `max_retries`
- Pre-2026-04 host adapters that haven't been upgraded

For every other workflow, prefer the typed orchestration + mutation verbs above. The documentation below still applies — it's the lower-level substrate the typed verbs call through.

## Preferred entry points (by host)

Use the orchestrator agent if your harness supports subagents:

| Host | Invocation |
|------|-----------|
| **Claude Code** | `Agent` tool with `subagent_type="brand-orchestrator"` (definition in `.claude/agents/brand-orchestrator.md`, mirrored at `skills/brand-gen/claude-agents/`) |
| **Pi / OpenClaw** | `/run brand-orchestrator "<task>"` (definition in `.pi/agents/brand-orchestrator.md`) |
| **Cursor / Codex / other** | Read `.claude/agents/brand-orchestrator.md` into context and follow its Manual Flow Contract |
| **MCP hosts** | Prefer the agent route if available. If the host only has plain MCP tools (no subagent support), walk the phases manually — see "Manual chain for hosts without subagents" below. |

**If you're an agent reading this skill and the user asked for brand material work**: your first move is to read `.claude/agents/brand-orchestrator.md` (or `.pi/agents/` for Pi) and follow the Mandatory Generation Sequence in it. Do **not** jump straight to `bgen pipeline`. The sequence is the product; the CLI is the substrate.

## Manual chain for hosts without subagents

If your harness cannot spawn subagents, walk the chain manually in this order. Each step is a `bgen` command, run from the repo root with `source .venv/bin/activate &&` prefixed:

```text
1. Explorer         context-snapshot, show-blackboard, show (recent versions)
2. Philosopher      check design-philosophy.md; export-design-tokens (WCAG gate);
                    read custom-scratchpad.md; if route is hybrid or inspiration,
                    inspiration-status and extract-inspiration + consolidate if pending
3. Router           route-request
4. Planner          suggest-role-pack, suggest-layout, plan-draft
5. Critic           critique-plan, validate-brand-fit; stop if blocking issues
6. Cinematographer  (video materials only) six-element prompt assembly +
                    seven-rule validation from references/seedance-shot-design.md
7. Generator        build-generation-scratchpad, generate
8. Critic           critique-rubric, submit-critique, feedback
9. Orchestrator     evolve
```

The MCP tool surface (`brand_*`) mirrors each `bgen` command one-to-one, so MCP hosts walk the same chain with tool calls instead of shell commands.

## Preferred MCP server

```bash
python3 -m brand_gen.brand_iterate_mcp
```

Most CLI commands are exposed as MCP tools with a `brand_` prefix (`brand_pipeline`, `brand_list`, `brand_review`, etc.). Names are customized for host ergonomics in a few cases.

## Agent bootstrap for your session

Paste this into a fresh agent session before asking for any brand work. Pick the block that matches your host.

**Claude Code:**
```text
For any brand material work in this session, use the Agent tool with
subagent_type="brand-orchestrator". Do not call `bgen pipeline` directly.
Start by reading .claude/agents/brand-orchestrator.md.
```

**Pi / OpenClaw:**
```text
Use /run brand-orchestrator "<task>" for all brand material requests.
Manual chain fallback: /chain brand-explorer -> brand-philosopher -> brand-router -> brand-planner -> brand-critic -> brand-generator -> brand-critic
```

**CLI-only or MCP-only agents (no subagent support):**
```text
For all brand material work, walk the manual chain in skills/brand-gen/SKILL.md
under "Manual chain for hosts without subagents". If you call `bgen pipeline`
directly without the preflight chain, you will skip the philosopher WCAG gate,
the inspiration-readiness check, and the cinematographer validation. The
pipeline will emit a loud stderr warning when this happens.
```

## Start every session here

Before generating anything, inspect the active workspace.

```bash
bgen context-snapshot --format json
bgen workspace-status --format json
bgen capabilities --format json
bgen show-session-summary --format json
```

Use them in this order:

- `context-snapshot` — canonical machine-readable workspace context
- `workspace-status` — root alignment and plugin/session warnings
- `capabilities` — current material/model/tool surface
- `show-session-summary` — human-readable current state and recent artifact pointers

## Agent config

Pi agents read two config sources:
- `.brand-gen-local.json` at the repo root — machine-specific paths (`repo_root`, `vault_paths`, `brand_vault_paths`, `brand_knowledge_base_paths`). Created automatically during setup. If missing, Pi agents fall back to the current working directory and skip vault sync.
- `brand-profile.json` → `creative_context` — brand-specific creative defaults (quality benchmarks, concept categories, metaphor vocabulary, optional `knowledge_base_paths` / `source_vault_paths`). Seeded on brand creation, persists with the brand.

If you need to create `.brand-gen-local.json` manually, see `.brand-gen-local.json.example`.
`context-snapshot` exposes merged, brand-scoped source docs as `source_knowledge`;
philosopher/interviewer agents should read those paths before planning when present.

## Onboarding — pick the right path

### Step 0 — ensure the workspace exists

```bash
bgen init --brand-name "<optional-brand-key>"
```

### Path A — existing saved brand

```bash
bgen list-brands --format json
bgen use <brand-key>
```

If you want a sandboxed exploration instead of mutating the saved brand directly:

```bash
bgen start-testing \
  --session-name "<name>" \
  --brand <brand-key> \
  --goal "<goal>"
```

### Path B — repo, docs bundle, or design-memory source available

```bash
bgen init --brand-name "<key>"
bgen extract-brand --project-root <path> --brand-name "<key>"
bgen use <key>
```

If the project has a `.design-memory/` folder or useful CSS variables:

```bash
bgen parse-design-memory --path <project-or-design-memory> --format json
bgen extract-css-variables --path <project-root> --format json
```

### Path C — no brand yet, start from conversation

```bash
bgen create-brand \
  --name "<brand-name>" \
  --description "<what the product is and who it serves>" \
  --tone "calm,technical,trustworthy" \
  --palette "#1A6B6B,#C85A2A"
```

Prefer `create-brand` when the user wants a durable saved brand. Use `start-testing --working-name ...` only when they explicitly want a temporary sandbox first.

## Routing — match the user's intent to the right workflow

For the full orchestrated pipeline with quality gate, design philosophy, and learning loop, load `skills/brand-gen-orchestration/SKILL.md` in addition to this skill. The orchestration skill wraps the core workflow here with a stricter 6-phase pipeline.

If your host is not running the Pi subagents directly, manually emulate `.pi/agents/brand-orchestrator.md` in this order:

1. explorer behavior — `context-snapshot`, `show-blackboard`, recent winners, workspace state
2. router behavior — choose the route before planning
3. planner behavior — build the plan draft
4. critic behavior — critique the plan before generation
5. generator behavior — only generate after approval

Default evidence to use in that flow:
- the active brand logo / resolved brand mark
- proven winning prior versions when they exist
- blackboard recipe hints and learning summaries
- no direct freehand generation before the plan is critiqued

```text
User wants to...
├─ Generate one asset
│  └─ pipeline
├─ Inspect route/plan/prompt stages before rendering
│  └─ route-request → plan-material / plan-draft → critique-plan → build-generation-scratchpad → generate
├─ Build a coordinated family of materials
│  └─ plan-set → validate-brand-fit / validate-set → generate-set
├─ Figure out messaging or copy before visuals
│  └─ load brand-content-ideation skill, then ideate-messaging / ideate-copy
├─ Explore logo / wordmark / lockup work
│  └─ load brand-gen-logo skill
├─ Review an existing output
│  └─ review-brand or critique-rubric → submit-critique
├─ Iterate on a previous version
│  └─ feedback + pipeline --source-version <vN>
├─ Extend an approved still
│  └─ derive-video / derive-mockup
├─ Capture product truth or inspiration
│  └─ shotlist / capture-product / extract-inspiration / consolidate-inspiration
└─ Mine an existing design system
   └─ parse-design-memory / extract-css-variables / diff-design-memory
```

Run `bgen types` for the canonical material list.

## Core operating principles

### 1. Brand truth before presentation truth

Lock the real brand anchors first:

- what the product actually is
- who it serves
- what message this material must communicate
- which claims or product details are approved

Let references teach framing, hierarchy, motion, and finish — not the core truth.

### 2. Messaging before imagery

For copy-bearing materials, resolve what the asset should say before you ask the image model to render it.

```bash
bgen ideate-messaging --format json
bgen ideate-copy --material-type x-feed --goal "Launch announcement" --format json
bgen update-messaging --format json
```

### 3. Saved brands and testing sessions serve different jobs

- **Saved brand** = durable brand memory under `.brand-gen/brands/<brand>/`
- **Testing session** = sandboxed workspace under `.brand-gen/sessions/<session>/brand-materials/`

Use sessions when exploring. Use saved-brand mode when working directly on the durable brand memory.

Implementation rule set:

- Never overwrite an existing saved-brand `brand-profile.json` just to bootstrap missing schema.
- If a saved brand is missing fields like `creative_context`, prefer `bgen start-testing --brand <brand-key>` and patch the session copy instead.
- Only migrate the durable saved brand profile when the user explicitly asked for that repair.
- If the request is actually for a different brand, create a new saved brand instead of mutating the current one.

### 4. Choose a composition mechanic, not just a vibe

Before writing the prompt seed, decide the dominant move.

```bash
bgen suggest-layout --material-type campaign-poster --format json
bgen suggest-role-pack --material-type campaign-poster --format json
```

## Optional source-vault / philosophy workflow

If richer brand materials live outside the repo, set `BRAND_SOURCE_VAULT` in `.env`.

Note: Pi agents use `vault_paths` in `.brand-gen-local.json` for the same purpose. If you use Pi, set `vault_paths`. If you use the CLI directly, set `BRAND_SOURCE_VAULT`. Both can coexist — they point at the same kind of source material through different configuration paths.

Use it for things like:

- positioning notes
- metaphor catalogs
- audience profiles
- approved website copy
- narrative arcs
- design-philosophy notes

A good design philosophy is cultivated from those sources, not invented from thin air. If you maintain one, store it with the active brand and translate it into:

- prompt-seed language
- preserve / push / ban rules
- critique criteria

Do **not** paste long philosophy prose directly into image prompts. Extract the useful material words, composition rules, and quality signals.

## Prompt-seed guidance

Good prompt seeds are compact creative briefs, not pixel-placement specs.

Pattern:

```text
{one dominant visual idea}, {real-world design analog}, {material truth}, {quality booster}
```

Good:

- `Monumental editorial poster, inspired by museum exhibition graphics, warm mineral paper texture, masterful restraint`
- `Type-dominant launch card, like a serious financial newspaper front page, cream stock and ink bleed, precise hierarchy`

Avoid:

- exact pixel positions
- angles and percentages
- long lists of tiny layout instructions
- visible copy you have not already resolved elsewhere

## Pre-flight checklist

Run this before generating:

```bash
bgen context-snapshot --format json
```

Check for:

1. **Workspace correctness** — are you in the intended saved brand or testing session?
2. **Inspiration readiness** — if inspiration sources are configured but not extracted, extract and consolidate first.
3. **Identity freshness** — if `identity_rebuild_recommended` appears, rebuild before generating.
4. **Reference fit** — if all refs are UI screenshots but the target is a poster/brand-scene, add better references or rely on inspiration memory.
5. **Score hygiene** — if versions are piling up without feedback, the learning loop is broken.
6. **Novelty** — check recent outputs so you do not repeat the same composition.

Useful commands:

```bash
bgen show --format json --latest 10
bgen compare --top 6
bgen improvement-questions --format json
```

## Direct `bgen pipeline` (scripting and CI bypass)

`bgen pipeline` runs the same underlying generation in-process but **skips the agent reasoning between phases**. Use it for scripts, CI, or debugging — not as the default path for interactive brand work. When invoked without orchestrator preflights, it emits a loud stderr warning and records the bypass to the run ledger.

**What you lose by calling it directly:** the philosopher's WCAG gate on the brand's palette, the inspiration-readiness check (sources configured but not extracted will default to deterministic-only analysis unless the pipeline's hard-gates catch it), the cinematographer's seven-rule shot validation for video materials, and the critic's P1 pushback on the plan before generation.

```bash
# Acknowledge the bypass explicitly to silence the advisory:
bgen pipeline \
  --bypass-orchestrator --reason "CI smoke test" \
  --material-type x-feed \
  --goal "Launch announcement" \
  --mode hybrid \
  --format json \
  --open
```

Helpful flags:

- `--bypass-orchestrator --reason "<one-line>"` — acknowledge the skipped agent chain; records the bypass to the run ledger so later diagnosis knows why a run didn't see orchestrator context
- `--source-version v012` — iterate from a prior version
- `--route <route_key>` — override auto-routing
- `--base-image /path/to/image` — edit/overlay mode
- `--prompt-seed "..."` — inject a concise creative brief
- `--mechanic "..."` — lock one dominant system move
- `--allow-blocking` — continue past blocking scratchpad findings only when explicitly justified
- `--critique-mode advisory` — inspect issues without strict blocking

Interpret the result:

- `stopped_at == "complete"` → generation finished
- `stopped_at == "critique"` → blocked before generation; inspect findings and fix the plan

**Preferred path for interactive work is still the orchestrator agent** — see the "Preferred entry points" table at the top of this skill.

## Manual workflow — inspect every stage

Use this when you want to debug route choice, prompt assembly, or review gates.

```bash
bgen route-request --material-type x-feed --goal "Launch announcement" --format json
bgen plan-material --material-type x-feed --goal "Launch announcement" --format json
bgen plan-draft --material-type x-feed --goal "Launch announcement" --format json
bgen critique-plan --plan /abs/path/to/plan-draft.json --format json
bgen build-generation-scratchpad --plan /abs/path/to/plan-draft.json --format json
bgen generate --scratchpad /abs/path/to/scratchpad.json
```

Also useful for prompt inspection:

```bash
bgen resolve-prompt --plan /abs/path/to/plan.json --format json
bgen review-prompt --plan /abs/path/to/plan.json --format json
```

## Review and quality gate

The default review path is rubric-first:

```bash
bgen critique-rubric v12 --format json
bgen submit-critique v12 --critique-json /abs/path/to/critique.json --format json
```

When the optional DSPy scorer is installed (`pip install -e '.[scoring]'` + `OPENROUTER_API_KEY` in `.env`), prefer the scored path — it pre-populates axis scores, rationales, and the failure-reason synthesis via a vision LM:

```bash
bgen critique-rubric v12 --dspy-scorer --format json
```

Workflow:

1. run `critique-rubric` (optionally with `--dspy-scorer`)
2. inspect the image yourself
3. evaluate against the returned rubric (see v2 axes below)
4. save critique JSON
5. submit it with `submit-critique`

At minimum, the critique JSON should include:

- `approved`
- `p1`
- `p2`
- `p3`
- `text_accuracy`
- `text_issues`

Use `review-brand` when you want a richer review packet and a proposed score before persisting feedback:

```bash
bgen review-brand v12 --format json
```

### v2 scoring rubric

The canonical rubric lives in `brand_gen/scoring/rubric_registry.py` and is surfaced to agents via `bgen show-rubric --material-type <type> --format json`. Use it as the scoring contract — the DSPy scorer, the critic agent, and any planner building toward a quality target all read the same source of truth.

Universal axes (always scored, 1-5 each):

- `composition` — layout hierarchy, focal point, whitespace balance, one dominant gesture
- `brand_coherence` — palette, approved devices, mark usage, declared typography
- `restraint` — absence of generic premium-AI decoration (no glassmorphism, purple gradients, neon-on-dark, icon-grid clichés, invented text)
- `story_fidelity` — does the composition serve the stated brief and surface, not just look nice
- `meaning_clarity` — would a new visitor understand what this is about in 2-3 seconds; rejects "tasteful but meaningless" outputs

Material-specific overlay axes (add on top of the universal 5):

- **landing-hero** — `surface_fit`, `meaning_at_glance` · disqualifier: no product category legible within 3s
- **concept-illustration** — `system_logic_visible`, `brand_specificity` · disqualifier: generic abstract metaphor (floating cubes, glowing nodes, etc.) with no brand-specific vocabulary
- **brand-scene** — `process_implied`, `brand_specificity` · disqualifier: pure architectural mood with no evidence of process

Aggregation is min-biased: any axis <2 caps overall <=2, and any triggered disqualifier hard-fails the material. Plan and generate toward the overlay axes for your material type — `meaning_clarity`, `story_fidelity`, and `brand_specificity` are where generic "premium AI brand" outputs fail most often.

### v2 packet contract

- **`rubric_version` present (v2 packet)**: `axis_scores` + `axis_rationales` populated per axis, `overall_score` (min-biased), `decision` (`approve` / `iterate` / `reject`), `disqualifier_triggered` (bool), `why_user_might_dislike_if_polished` (the honest failure signal). Critic reviews and may override.
- **`rubric_version` absent (v1 packet)**: legacy 4-axis narrative (composition, material_truth, brand_coherence, restraint); critic scores from scratch.

### Scoring inspection commands (read-only)

```bash
bgen show-rubric --material-type concept-illustration --format json
bgen show-disagreements --bucket calibration_failure --limit 20 --format json
bgen scoring-status --format json
```

- `show-rubric` — dump the axis definitions + overlay + disqualifier rule for any material type
- `show-disagreements` — list recorded agent-vs-user disagreements from the brand's `scoring/disagreements.jsonl`
- `scoring-status` — summary of disagreement bucket counts, partition split, and weighted Cohen's kappa when enough data is present

## Feedback and iteration

Persist explicit user preference signals with `feedback`:

```bash
bgen feedback v17 --score 4 --notes "Strong direction, simplify the copy"
bgen feedback v18 --score 1 --status rejected --notes "Generic, invented copy"
```

Then iterate from the prior version:

```bash
bgen pipeline --material-type x-feed --source-version v17 --format json --open
```

Use these learning surfaces regularly:

```bash
bgen evolve --format json
bgen improvement-questions --format json
bgen update-iteration-memory --format json
```

## Sets and derivatives

### Coordinated sets

```bash
bgen plan-set --template launch-core --goal "New product launch" --format json
bgen validate-brand-fit --set /abs/path/to/set.json --format json
bgen validate-set --set /abs/path/to/set.json --format json
bgen generate-set --set /abs/path/to/set.json --parallel
```

### Derive motion from an approved still

```bash
bgen derive-video --source-version v17 --format json
```

### Derive a contextual mockup scene from an approved still

```bash
bgen derive-mockup --source-version v17 --format json
```

Treat mockups as generated scenes, not pixel-perfect compositing.

## Inspiration, reference, and product capture

### Inspiration

```bash
bgen extract-inspiration --category symbol
bgen consolidate-inspiration --format json
bgen inspiration-mode on
bgen example-sources --format json
bgen collect-examples --help
```

`consolidate-inspiration` is a standalone state update, not a pipeline stage.

#### Pinning primary buckets with `rebucket-inspiration`

When every inspiration source declares every bucket (composition, narrative_system, rendering_style), role-pack ranking degenerates into first-by-index and the same source ends up filling every role slot. Fix it per source:

```bash
bgen rebucket-inspiration --source pentagram-poster-house --primary composition --format json
bgen rebucket-inspiration --source pentagram-jigsaw --primary narrative_system --format json
bgen rebucket-inspiration --source koto-pairpoint --primary rendering_style --format json

# Fine-grained weights instead of a single primary bucket:
bgen rebucket-inspiration --source gretel-work --scores '{"composition": 0.6, "narrative_system": 0.4, "rendering_style": 0.3}' --format json

# Revert to legacy bucket_hints-only ranking for a source:
bgen rebucket-inspiration --source some-source --clear --format json
```

Sources with `primary_bucket` set receive a strong ranking bonus for their declared bucket, so `suggest-role-pack` picks a different source for each role slot instead of defaulting to the first-in-list. Sources with `bucket_scores` get fine-grained weights applied to the existing score formula.

### Product capture

```bash
bgen shotlist --product-name "<product>" --format json
bgen capture-product --url https://example.com/app --label home --open-folder
```

### Brand exploration

```bash
bgen explore-brand --material x-feed --top 4 --format json
```

## Share cards

### Rule

Use native image/video generation for normal brand materials.

Use `--render-backend html` only when the user explicitly wants a deterministic, source-derived share card.

### HTML share-card path

```bash
bgen pipeline \
  --material-type announcement-card \
  --render-backend html \
  --source-url "https://example.com/artifacts/<slug>" \
  --entity-type prompt \
  --proof-meta "UI systems" \
  --proof-row "Built for fast design decisions across product surfaces." \
  --design-variance 6 \
  --format json
```

Useful overrides:

- `--headline`
- `--subhead`
- `--cta`
- `--proof-title`
- `--proof-excerpt`
- `--proof-row`
- repeated `--proof-meta`
- `--proof-crop-path`
- `--skip-proof`
- `--dark-mode`
- `--layout-spec '{"columns":2,"proof_position":"right"}'`

This path uses card-data plugins plus Chrome headless rendering. It is not the old Stitch path.

## Session inspection and diagnostics

| Need | Command |
|------|---------|
| Machine-readable workspace view | `context-snapshot --format json` |
| Root / alignment warnings | `workspace-status --format json` |
| Human-readable workspace summary | `show-session-summary --format json` |
| Blackboard / latest decisions | `show-blackboard --format json` |
| Recent versions | `show --format json --latest 5` |
| Visual comparison board | `compare --top 6` |
| Prompt / metadata diagnostics | `diagnose v14 v15 --format json` |
| Workflow lineage | `show-workflow-lineage --workflow-id <id> --format json` |
| Reference-analysis cache | `show-reference-analysis --format json` |
| Iteration notes | `show-iteration-memory --format json` |
| Platform dimensions | `social-specs` |

## Host integration notes

- **Pi / OpenClaw / similar hosts**: if the host exposes native wrappers such as `brand_search`, `brand_execute`, `brand_status`, or `/brand-gen`, you can use them as wrappers around the same backend.
- **MCP hosts**: prefer the public `brand_*` tool surface.
- **CLI-first agents**: prefer `bgen ...`.
- Do **not** rely on private local subagents or untracked host files unless the current checkout explicitly ships them.

## What to avoid

- generating before confirming the active workspace
- skipping messaging on copy-bearing materials
- using UI screenshots as the only references for non-UI materials
- letting many unscored generations accumulate
- retrying `pipeline` blindly when `stopped_at == "critique"`
- solving exact-text problems with more prompt text instead of better process
- treating HTML share cards as the default output path
- assuming every host has the same private local agent setup
- committing machine-specific paths into skills, prompts, or docs
- **manually editing `custom-scratchpad.json`, `custom-scratchpad.md`, `learnings.json`, `iteration-memory.json`, or `brand-identity.json`** — always use the typed mutation verbs from the "Typed runtime" section (`bgen append-forbidden-pattern`, `bgen append-custom-scratchpad-note`, `bgen promote-learning`, `bgen promote-style-policy`, `bgen set-motion-grammar`, `bgen update-palette`, `bgen update-typography`, `bgen update-devices`, `bgen submit-review`). Direct edits bypass the run ledger and corrupt disagreement capture
- defaulting to `bgen pipeline` when `bgen orchestrate-material` would work — pipeline is the CI/scripting fallback, not the primary path

## Design tokens and WCAG

Every brand with a `brand-identity.json` palette can emit production-ready design tokens. The exporter generates a 50–950 shade scale per base color, a math-derived type scale, WCAG AA–audited semantic roles, and platform outputs.

```bash
bgen export-design-tokens --output-format css       --format json    # default CSS custom properties
bgen export-design-tokens --output-format tailwind  --format json    # Tailwind config
bgen export-design-tokens --output-format json      --format json    # flat JSON tokens
bgen export-design-tokens --output-format w3c       --format json    # W3C DTCG
```

Output lands at `.brand-gen/brands/<active>/design-tokens/design-tokens.{ext}`. The JSON response includes a `.wcag` block with full audit results; errors block emission unless `--skip-audit` is passed. For the full reasoning, reference text, and algorithms, load `references/design-tokens.md`.

The HTML share-card renderer auto-consumes `design-tokens.css` when present. Agents should run this in Phase 1 of any new brand setup; the philosopher owns fixing any WCAG errors by adjusting `brand-identity.json` before downstream generation starts.

## Seedance shot-design for video

For any video material (`short-video`, `derive-video`, `launch-film`, `motion-card`, `announcement-video`, `brand-bumper`), use the `brand-cinematographer` agent. It reads the motion grammar that `brand-philosopher` writes into `custom-scratchpad.md` from `references/seedance-shot-design.md` (director tokens, cinematography dictionary, 3-layer lighting recipes, organic-imperfection anchors, seven-rule validation).

Models for seedance-based pipelines are registered in `brand_gen/models.json` (`seedance-2-pro`). The `launch_producer.py` brief-driven multi-shot pipeline enforces a seven-rule validation on every shot prompt via `brand_gen/seedance_validation.py` before firing generation.

## Reference files

Load these only when needed:

- `references/commands.md` — command cheatsheet, MCP naming, key gotchas
- `references/recipes.md` — multi-step workflows and practical examples
- `references/design-philosophy-framework.md` — cultivating a design philosophy from source material
- `references/design-tokens.md` — type scale math, palette scale math, WCAG algorithm, W3C DTCG file layout, smart font fallback pattern (fully self-contained, distilled from dylanfeltus/design-tokens + pbc-os/brand-identity + anthropics/brand-guidelines)
- `references/seedance-shot-design.md` — English-only cinematography dictionary, director style library, 3-layer lighting, motion grammar, and seven-rule validation checklist (distilled from openclaw/seedance-shot-design)
- `references/interview-protocol.md` — interview principles, seed capture format, coverage map, question format, elenchus technique, hard blocks (distilled from PeterSalvato/formwork + stympy/interview-me + wunki/amplify/interview). Used by brand-philosopher Step 3 and by the brand-interviewer agent.
- `references/poetic-synthesis.md` — close reading, metaphor analysis, image/symbol extraction, sound and rhythm, silence, voice directive, metaphor-to-image bridge (distilled from majiayu000/poet-analyst + majiayu000/greek-philosopher). Used by brand-philosopher Step 2 (Synthesis) and Step 4 (Name the Movement).
- `references/motion-and-polish.md` — narrow-scope distillation of Emil Kowalski's design-engineering skill. Only two parts of that upstream skill apply to brand-gen: (1) HTML share-card CSS polish (encoded in `html_design_engineering` / `html_taste_directives` in `data/prompt_fragments.json`), and (2) the brand-critic's Before/After/Why critique table format (already used as `before_after_diffs` in the critique JSON). The rest of emil's skill is React/CSS animation work — not relevant to prompt engineering for Flux/Recraft/Seedance. Load the full `.agents/skills/emil-design-eng/SKILL.md` only when hand-coding CSS around a brand-gen asset.

For models, surfaces, and file layout, load the companion skill:

- `skills/brand-gen-reference/SKILL.md`

## Multi-agent orchestration (pi or Claude Code)

Brand-gen ships seven specialist subagents that implement the 6-phase pipeline (prepare → plan → validate → generate → critique → evolve). Two parallel distributions live in the repo:

- **pi** — `.pi/agents/brand-*.md` (7 agents) + `.pi/settings.json` with Anthropic model overrides. Invoke via `/run brand-orchestrator <task>` or `/chain brand-explorer -> brand-planner -> brand-critic -> brand-generator`.
- **Claude Code** — `skills/brand-gen/claude-agents/brand-*.md` (canonical), mirrored at `.claude/agents/brand-*.md` at the repo root. Invoke via the `Agent` tool with `subagent_type="brand-orchestrator"` (or any of the six specialists). See `skills/brand-gen/claude-agents/README.md` for install / adoption options.

The pi and Claude Code copies share identical markdown bodies; only the frontmatter differs (Claude Code uses tool arrays and Claude model IDs, and drops pi-only fields). Keep them in sync when either side changes.

## Nano-banana-2 creative pipeline (direct generation)

For product-led material types (browser-illustration, announcement-card, product-banner, landing-hero, feature-illustration, carousel-slide, linkedin-feed, x-feed), one effective pattern is **nano-banana-2 with reference images** called directly via `bgen image`:

```bash
bgen image \
  -m nano-banana-2 \
  -p "<narrative prompt describing the composition>" \
  -i .brand-gen/brands/<active>/logo.png \
  -i .brand-gen/brands/<active>/product-shots/<relevant-page>.png \
  -i <style-reference-image> \
  --aspect-ratio <ratio> \
  -o <output-path>
```

**Rules for direct nano-banana generation:**
- Include the brand logo (`.brand-gen/brands/<active>/logo.png`) as a reference image when it exists
- For product-led materials, include a relevant product screenshot when one exists
- Prefer a strong prior output or curated style reference rather than a vague moodboard
- Use narrative paragraph prompts, not keyword lists
- The prompt should describe the composition as a story, not a spec sheet
- If you include a small brand mark, keep it subordinate and never duplicated
- Do not add redundant URL text when a QR code or stronger CTA already handles the action
- Ask the user for real data/stats rather than hallucinating numbers
