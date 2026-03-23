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

Preferred CLI: `bgen ...` or `python3 -m mcp.brand_iterate ...`

Preferred MCP server: `python3 -m mcp.brand_iterate_mcp`

Most CLI commands are also exposed as MCP tools with a `brand_` prefix. A few names are customized for host ergonomics (for example `list-brands` → `brand_list`, `review-brand` → `brand_review`, `pipeline` → `brand_pipeline`).

Do **not** assume host-private local agents like `brand-orchestrator` exist unless the current checkout explicitly ships them and you are running in a Pi workspace that uses `.pi/agents/`. The public repo's default workflow is the `bgen` / MCP command surface itself. If a Pi workspace wraps that surface with local agents, those agents read machine-local config from `.brand-gen-local.json`.

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
- `.brand-gen-local.json` at the repo root — machine-specific paths (`repo_root`, `vault_paths`). Created automatically during setup. If missing, Pi agents fall back to the current working directory and skip vault sync.
- `brand-profile.json` → `creative_context` — brand-specific creative defaults (quality benchmarks, concept categories, metaphor vocabulary). Seeded on brand creation, persists with the brand.

If you need to create `.brand-gen-local.json` manually, see `.brand-gen-local.json.example`.

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

## Default workflow — single asset

Use `pipeline` for most normal generation tasks.

```bash
bgen pipeline \
  --material-type x-feed \
  --goal "Launch announcement" \
  --mode hybrid \
  --format json \
  --open
```

Helpful flags:

- `--source-version v012` — iterate from a prior version
- `--route <route_key>` — override auto-routing
- `--base-image /path/to/image` — edit/overlay mode
- `--prompt-seed "..."` — inject a concise creative brief
- `--mechanic "..."` — lock one dominant system move
- `--allow-blocking` — continue past blocking critique findings only when explicitly justified
- `--critique-mode advisory` — inspect issues without strict blocking

Interpret the result:

- `stopped_at == "complete"` → generation finished
- `stopped_at == "critique"` → blocked before generation; inspect findings and fix the plan

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

Workflow:

1. run `critique-rubric`
2. inspect the image yourself
3. evaluate against the returned rubric
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

Judge outputs on:

- clarity of composition
- material truth
- brand coherence
- restraint
- whether the asset does the job it was made for

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

## Reference files

Load these only when needed:

- `references/commands.md` — command cheatsheet, MCP naming, key gotchas
- `references/recipes.md` — multi-step workflows and practical examples
- `references/design-philosophy-framework.md` — cultivating a design philosophy from source material

For models, surfaces, and file layout, load the companion skill:

- `skills/brand-gen-reference/SKILL.md`

## Nano-banana-2 creative pipeline (direct generation)

For product-led material types (browser-illustration, announcement-card, product-banner, landing-hero, feature-illustration, carousel-slide, linkedin-feed, x-feed), one effective pattern is **nano-banana-2 with reference images** called directly via `python3 mcp/generate.py image`:

```bash
python3 mcp/generate.py image \
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
