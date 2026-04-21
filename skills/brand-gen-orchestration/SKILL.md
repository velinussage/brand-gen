---
name: brand-gen-orchestration
description: >
  Full 6-phase brand material generation pipeline: prepare → plan → validate →
  generate → critique → evolve. Converts a multi-agent workflow into sequential
  instructions any single agent can follow.
  USE WHEN: generating brand materials, creating branded assets, running the brand
  pipeline, iterating on brand visuals, producing concept illustrations, social posts,
  campaign posters, brand scenes, announcement cards, or any visual brand deliverable.
  Also use when asked to "run a generation", "create brand content", "make a poster",
  "illustrate a concept", or any request that produces branded image output through bgen.
  DO NOT USE WHEN: setting up brand-gen for the first time (use brand-gen-setup),
  looking up model specs or surface dimensions (use brand-gen-reference),
  doing logo/wordmark work (use brand-gen-logo), or ideating content briefs
  (use brand-content-ideation).
compatibility:
  tools: [Bash, Read, Write]
---

# Brand-Gen Orchestration Pipeline

This skill encodes the 6-phase generation pipeline that produces brand materials through structured preparation, planning, validation, generation, critique, and learning.

Every phase exists for a reason. Preparation prevents repeating mistakes. Planning encodes creative intent. Validation catches contradictions cheaply. Critique enforces a quality bar. Evolution compounds learnings across runs.

## Typed runtime (2026-04+, preferred surface)

After the typed-agentic-runtime refactor (Phases 1-6 of the 2026-04 plan), the entire 6-phase pipeline is exposed as **typed MCP/CLI tools with structured responses**. Pin to these verbs instead of scripting the legacy chain below — the legacy chain is the fallback for CI/scripting, not the primary path.

### Orchestration (7 verbs — run the pipeline)

```bash
# Convenience: runs all six phases to a natural stop.
bgen orchestrate-material \
  --material-type concept-illustration \
  --mode hybrid \
  --source-version v018 \      # optional: iterate from a prior version
  --format json
# Returns: {run_id, stages_completed, stop_reason, next_action, artifacts}
```

`stop_reason` enum — branch on this, do not parse narrative phase outputs:

| stop_reason | Meaning | What to do next |
|---|---|---|
| `approved` | Review accepted. | Report `version_id` + `image_paths`. Ask user for a score. |
| `blocking_findings` | Validate raised blocking issues. | Read `artifacts.critique.checks.blocking`; fix with typed mutations below; re-run. |
| `iterating` | Review returned `decision: iterate`. | Feed `before_after_diffs` rows into next run's mutations; re-run with `--source-version`. |
| `max_retries` | Orchestrator hit its retry ceiling. | Fall through to per-stage tools to debug. |
| `needs_user_input` | Ambiguity the orchestrator cannot resolve. | Surface `next_action` to the user. |

Per-stage fall-through (6 tools) — use these only when `orchestrate-material` stops with `max_retries` or you need stage-level A/B testing:

```bash
bgen prepare-run   # Phase 1 → {brand_dna_summary, applicable_learnings, readiness_issues, route, next_action}
bgen plan-run      # Phase 2 → {plan_id, plan_summary, next_action}
bgen validate-run  # Phase 3 → {status: ok|blocked, blocking_issues, warnings, critique_id, next_action}
bgen execute-run   # Phase 4 → {version_id, image_paths, stopped_at, scratchpad_path, next_action}
bgen review-run    # Phase 5 → {axis_scores, decision, before_after_diffs, visual_review_status, next_action}
bgen evolve-run    # Phase 6 → {learnings_promoted, disagreements_logged, improvement_questions, next_action}
```

Each response's `next_action` is a direct hint to the next tool. Follow it unless you're intentionally A/B-testing a stage.

### v2 review decision rule (thresholds)

When `review-run` (or `critique-rubric --dspy-scorer`) returns a packet with `rubric_version` present:

1. `disqualifier_triggered == true` → **REJECT** (overall_score is forced to 1; skip axis arithmetic entirely).
2. `overall_score < 3` → **ITERATE**.
3. `overall_score >= 3` AND `disqualifier_triggered == false` → **APPROVE**.

`overall_score` is min-biased: any axis <2 caps overall at ≤2.

`before_after_diffs` is the actionable fix list on ITERATE. Each row is `{principle, before, after}` where `principle` is a rubric axis or slop-pattern name. Feed each row into the next iteration as either:

- **Durable** (preferred) — `bgen append-forbidden-pattern` for `before` clauses + `bgen append-custom-scratchpad-note --section composition` for `after` clauses. Persists across runs.
- **Ephemeral** — `--ban "<before>"` and `--push "<after>"` inline on the next `orchestrate-material` call. One-run only.

Use durable when the `before` is a recurring slop tell. Use ephemeral when it's run-specific.

### Mutation (9 typed verbs — replace every direct file edit)

**Never manually edit `custom-scratchpad.json`, `custom-scratchpad.md`, `learnings.json`, `iteration-memory.json`, or `brand-identity.json`.** Call the typed verb. Every tool supports `--dry-run` returning the same response shape so you can preview.

| Verb | Replaces | Typical use |
|---|---|---|
| `bgen append-forbidden-pattern --pattern "..." --reason "..."` | Hand-edits to `custom-scratchpad.json` forbidden_patterns | Ban a slop tell (e.g. "floating gradient orbs") |
| `bgen append-custom-scratchpad-note --section {global,motion,typography,composition} --text "..."` | Hand-edits to `custom-scratchpad.md` sections | Add a composition directive or motion rule |
| `bgen promote-learning --bucket {modelPreferences,failurePatterns,...} --text "..."` | Hand-edits to `learnings.json` | Promote a winning setup or failure pattern |
| `bgen promote-style-policy --material-type --reference-policy rotating_anchor_set --anchor v1 --anchor v2 ...` | Hand-edits to `styleReferencePolicies` | Declare a rotating anchor set for a material |
| `bgen update-palette --role {primary,secondary,accent,...} --hex "#..."` | Hand-edits to `brand-identity.json` `brand_colors` + WCAG re-audit | Change a palette role |
| `bgen update-typography --role {display,body,mono} --family "..." --fallback "..."` | Hand-edits to `brand-identity.json` typography | Change a font role |
| `bgen update-devices --add/--remove "<device>"` | Hand-edits to approved devices list | Promote or retire a brand device |
| `bgen set-motion-grammar --director "..." --favored "..." --banned "..." --intensity {low,medium,high}` | Hand-edits to motion-grammar section | Author or revise motion grammar |
| `bgen submit-review <version-id> --critique-json <path>` | Alias for `submit-critique` | Submit a v2 critique packet |

### Inspection (7 read verbs)

```bash
bgen context-snapshot --format json        # canonical workspace snapshot — run at session start
bgen show-blackboard --format json         # active brief + decisions
bgen show-iteration-memory --format json   # positive/negative examples + rotation state
bgen show-rubric --material-type <t> --format json  # scoring contract before planning/critiquing
bgen show-disagreements --format json      # agent-vs-user disagreements (calibration)
bgen scoring-status --format json          # weighted Cohen's kappa + agreement rate
bgen capabilities --format json            # available tools + material types
```

### Rule: typed verb before file edit

Every time this skill or an agent instructs "edit this JSON/markdown file", stop. Pick the typed verb from the mutation list above. If no typed verb exists, the skill is out of date — file that gap instead of hand-editing. Direct file edits bypass the run ledger, skip deprecation warnings, and corrupt disagreement capture.

### When to fall through to the legacy chain below

The sequential `plan-draft → critique-plan → build-generation-scratchpad → generate → feedback → pipeline → evolve` chain documented in the phases below remains supported for:

- CI/scripting that needs a single blocking `bgen pipeline` call
- Debugging individual stages when `orchestrate-material` stops with `max_retries`
- Pre-2026-04 host adapters that haven't been upgraded

For every other workflow — **especially agents reading this skill at runtime** — prefer the typed orchestration + mutation verbs above. The 6-phase documentation below is the lower-level substrate the typed verbs call through, kept here so phase-level debugging stays possible.

## Setup

Run all `bgen` commands from the repo root. Prefix every command with
`source .venv/bin/activate &&`. Use `--format json` for structured output.

Read `.brand-gen-local.json` at repo root for machine-specific paths (vault paths,
repo root). All brand data lives in `.brand-gen/brands/<active>/`.

When a host does not provide the Pi subagents directly, emulate the same orchestration chain manually:

1. explorer behavior — inspect workspace and blackboard state
2. router behavior — choose the route
3. planner behavior — draft the plan
4. critic behavior — critique the plan before generation
5. generator behavior — generate only after approval

Use the active brand logo, proven winning prior versions, and blackboard recipe hints as your default evidence base. Do not skip straight to freehand generation before the plan has been critiqued.

## Pi-Style Orchestration Is Mandatory

Do not treat the Pi-style chain as a suggestion. For any real generation request, you must complete these stages in order:

1. **Explorer** — inspect workspace, blackboard, learnings, prior approved versions
2. **Router** — choose the route and explain why
3. **Planner** — create the plan draft using the evidence base
4. **Critic** — run plan critique and brand-fit validation
5. **Generator** — generate only after the plan is approved

If any of steps 1-4 are skipped, the workflow is invalid. Do not generate anyway.

## Required Evidence Base Before Generation

Before you generate anything, you must inspect and apply all of the following when they exist:

- `blackboard.json` → `learning_summary[material]`
- `blackboard.json` → `material_recipes[material]`
- `blackboard.json` → `active_brief` when relevant
- `learnings.json` model preferences for the requested material
- at least **2 prior approved / high-scoring versions** for the same material or adjacent material
- the active brand logo path
- for `inspiration` mode, actual configured inspiration sources or explicitly approved prior exemplars that are being translated
- `learnings.json` → `styleReferencePolicies` / style-lock records for the requested material or adjacent family
- any product screenshots or proof assets required for the material type

Treat these as inputs, not background reading. The plan must visibly reflect them.

## Required Pi Orchestration Memo

Before generation, produce a compact orchestration memo in your reasoning / working notes that includes:

- chosen material type
- chosen route
- workspace state summary
- blackboard learnings applied
- style-anchor policy applied (or explicit statement that none exists)
- prior versions referenced
- inspiration / references selected and what each contributes
- key preserve / push / ban decisions
- validation result

If you cannot produce this memo, you are not ready to generate.

## Hard Rules

- **Do not generate from abstract brand language alone when approved exemplars exist.**
- **Do not use blackboard learnings as advisory only** — convert them into concrete plan constraints.
- **Do not fall back to ad hoc direct model calls** (`generate.py`, manual composites, external edits) unless the structured orchestration path is blocked and you explicitly state why.
- **Do not use deterministic composites as a substitute for the pipeline** unless the task itself is a deterministic composite / proof layout task.
- **Do not skip validation because a prompt “seems fine.”**
- **Do not mutate saved brand memory during orchestration** (`brand-profile.json`, `brand-identity.json`, learnings, blackboard) unless the user explicitly asked for a repair/update or you are in a disposable testing session.
- **Do not treat “inspiration mode” as valid when no real inspiration sources are configured.** If `selected_inspiration_ids` is empty, either reroute explicitly or stop and report the gap.
- **Do not let the plan rely on reference roles the selected model/wrapper cannot actually carry.** If the route depends on image refs but the wrapper only uses them for prompt routing/context, treat that as a validation risk and prefer reroute/block over wishful thinking.
- **Do not drop a proven style anchor when the learnings say it is required to prevent drift.** Treat required style references as first-class constraints, not optional taste notes.

## Step 0: Read the Workspace

Before anything else, understand where you are:

```bash
source .venv/bin/activate && bgen context-snapshot --format json
```

This returns: active brand, recent versions, current session state, brand profile
summary, and identity highlights. Read the output — it tells you what exists and
what is missing.

## The 6-Phase Pipeline

```
┌─────────┐   ┌──────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌────────┐
│ PREPARE │──▸│ PLAN │──▸│ VALIDATE │──▸│ GENERATE │──▸│ CRITIQUE │──▸│ EVOLVE │
└─────────┘   └──────┘   └──────────┘   └──────────┘   └──────────┘   └────────┘
     │                        │                              │
     │                        ▼                              ▼
     │                   max 2 plan                     max 2 retry
     │                   revisions                      cycles
     ▼
 philosophy
 creation if
 missing
```

### Phase 1: Prepare

Gather context, apply learnings, prevent repetition. Full details:
[references/phase-1-prepare.md](references/phase-1-prepare.md)

Critical steps (do not skip):

1. **Explorer pass first** — Before planning, inspect:
   - `bgen context-snapshot --format json`
   - the active `blackboard.json`
   - the active `learnings.json`
   - at least 2 relevant prior approved / high-scoring versions and their images

   Summarize what worked, what failed, and what must remain locked.

2. **Creative-context check (non-mutating by default)** — Read `brand-profile.json`.
   If `creative_context` is missing in a saved brand workspace, report the gap and use
   ephemeral defaults in your memo for this run. Only write the block back when:
   - the user explicitly approved the repair, or
   - you are inside a disposable testing session.

3. **Design philosophy check** — Read `design-philosophy.md` from the active brand
   directory. If it does not exist, create one before proceeding (see
   [references/philosophy-workflow.md](references/philosophy-workflow.md)). Extract
   material metaphors, composition rules, and quality boosters for use in planning.

4. **Learnings check** — Read `learnings.json` for `modelPreferences` matching the
   requested material type. Apply winning setups (mode, model). Also read any
   `styleReferencePolicies` / style-lock records for the material. If learnings say
   a specific prior version is the mandatory style carrier, keep it in the plan even
   when the concept/mechanic changes.

5. **Blackboard check** — Read `blackboard.json` for:
   - `learning_summary[material]`
   - `material_recipes[material]`
   - `active_brief`

   Convert these into explicit preserve / push / ban / mode / reference decisions.
   Do not continue with only a generic paraphrase.

6. **Inspiration-set pass (mandatory for illustration-first work)** — Run `bgen inspiration-status --format json` on every non-motion run, not just hybrid/inspiration. For standalone illustration requests ("just the illustration", "not the full landing page", "right-side artwork", "standalone illustration"), you must inspect and name an inspiration set before planning:
   - at least 3 inspiration sources total
   - at least 1 composition / spatial ref
   - at least 1 narrative-system ref
   - at least 1 rendering / finish ref

   If that set is missing or weak, stop and report the gap instead of proceeding with generic planning.

7. **Concept diversity** — Read `creative_context.concept_categories`. Check recent
   generations. Auto-select the least illustrated concept if the caller did not
   specify one.

8. **Role pack and layout suggestions** — Run `bgen suggest-role-pack` and
   `bgen suggest-layout` for the material type. These provide composition references
   and surface strategy.

8. **Previous implementations review** — If approved exemplars exist, identify:
   - what visual mechanic is preserved
   - what brand anchor is preserved
   - what new variable is being explored

   Never attempt a “fresh” direction that discards all prior successful mechanics at once.

### Phase 2: Plan

Build an informed plan from preparation context. Full details:
[references/phase-2-plan.md](references/phase-2-plan.md)

Critical steps:

1. **Run routing explicitly** — Choose the route before drafting. Record why the route fits the material and evidence base.
   If the intended route is `inspiration` but the workspace has no configured inspiration
   sources, do not quietly pretend prior outputs alone satisfy that route. Either:
   - explicitly reroute to a prior-winner / brand-memory driven plan, or
   - stop and report that inspiration setup is missing.

   For illustration-only requests, do **not** route into strict page-scaffold patterns just because the artwork will later sit on a landing page. Bias toward a standalone illustration material and note that the user asked for artwork, not the full page. `feature-illustration` can still be valid, but only when explicitly constrained as standalone artwork rather than a page comp.

2. **Enrich the prompt seed** with philosophy metaphors — use material words as
   texture references, apply composition rules as structural guidance, end with
   craftsmanship boosters. Do NOT paste philosophy verbatim.

   For illustration-only requests, the planning memo must explicitly say:
   - artifact scope = illustration only
   - not a landing page / hero comp / browser mockup / screenshot-proof inset
   - which inspiration sources are serving composition, narrative/system, and rendering/style

3. **Enrich with blackboard and prior winners** — The prompt seed and flags must reflect:
   - blackboard success patterns
   - blackboard failure patterns
   - prior approved mechanics
   - required style-anchor versions
   - explicit brand-anchor decisions

4. **Run plan-draft** with all preparation context:
   ```bash
   source .venv/bin/activate && bgen plan-draft \
     --material-type <type> \
     --mode <mode from learnings or hybrid> \
     --purpose "<purpose>" \
     --prompt-seed "<enriched seed>" \
     --format json
   ```

5. **Review the plan JSON** — Is the creative direction specific? Are sources
   appropriate? Are there warnings? If generic, refine the seed and rerun once.

6. **Show the plan logic clearly** — The plan review must make clear:
   - which prior versions were referenced
   - which learnings were applied
   - which style anchor was required and why
   - which inspiration mechanics were borrowed
   - what is intentionally new versus intentionally locked
   - how the logo / brand mark is being preserved without sending it through the wrong semantic role

### Phase 3: Validate

Catch problems before spending on generation. Full details:
[references/phase-3-validate.md](references/phase-3-validate.md)

Run both checks:
```bash
source .venv/bin/activate && bgen critique-plan --plan <plan-path> --format json
source .venv/bin/activate && bgen validate-brand-fit --plan <plan-path> --format json
```

**P3-to-blocker promotions (MUST enforce):**

| Warning text | Action |
|-------------|--------|
| "Exact text request detected" | BLOCK — image models cannot reliably render specific text |
| "hybrid mode has been underperforming" | BLOCK if plan still uses hybrid — switch to winning mode |
| "text issues found from prior version" | BLOCK — do not repeat a failing text configuration |

**Design coherence check** — verify these are not contradictory:
- Model choice vs. text complexity needs
- Color/contrast vs. target surface (social needs high contrast at thumbnail size)
- Composition direction vs. aspect ratio (vertical needs vertical rhythm)

If BLOCKING: adjust plan parameters and re-validate. Max 2 plan revision iterations.
If warnings only: proceed but note them for post-generation review.

**No generation is allowed before a pass here.**

Also block or revise if either of these is true:
- the route claims `inspiration` but `selected_inspiration_ids` is empty and no explicit reroute was recorded
- the plan depends on reference roles that the chosen model/wrapper will not actually transport into generation

### Phase 4: Generate

Build scratchpad and generate. Full details:
[references/phase-4-generate.md](references/phase-4-generate.md)

```bash
source .venv/bin/activate && bgen build-generation-scratchpad --plan <plan-path> --format json
source .venv/bin/activate && bgen generate --scratchpad <scratchpad-path> --max-iterations 2
```

For interface materials (browser-illustration, landing-hero, product-banner,
feature-illustration): ALWAYS pass `--base-image <screenshot-path>`. Without a real
screenshot, the model invents fake UI that scores 1-2 every time.

**Exception:** if the user explicitly asked for illustration-only artwork that will later live on a landing page, do **not** choose an interface material just to justify `--base-image`. Re-route to a standalone illustration material, or use `feature-illustration` only with explicit standalone-art constraints, and use screenshots only as semantic truth anchors.

If the scratchpad has blocking issues, stop and report clearly. Do not generate
from a broken scratchpad.

If the generation path is blocked and you believe a deterministic fallback is appropriate, state:
- why the normal pipeline is blocked
- why the fallback matches the user’s requested artifact type
- what brand-truth constraints will still be preserved

Do not silently switch modes or tools.

### Phase 5: Critique

Apply the quality gate. Full details:
[references/phase-5-critique.md](references/phase-5-critique.md)

**Scoring rubric (1-5 each):**

| Axis | What it measures |
|------|-----------------|
| `composition` | Layout hierarchy, focal point, whitespace balance |
| `material_truth` | Does it serve the material type's purpose and surface? |
| `brand_coherence` | Palette accuracy, mark usage, approved motifs only |
| `restraint` | No invented text, no off-brand decoration, no stock feel |
| `philosophy_fit` | Does it feel like a work from the named movement? |

**AI slop check** — scan for these anti-patterns (each is an automatic ban directive):

| Anti-pattern | Ban directive |
|-------------|--------------|
| Purple/violet gradients | `--ban "purple gradients"` |
| Cyan-on-dark neon palette | `--ban "neon cyan accents on dark background"` |
| Glassmorphism/frosted glass | `--ban "glassmorphism, frosted glass panels"` |
| 3-column icon grid with circles | `--ban "3-column icon grid with colored circles"` |
| Glossy 3D when brief says flat | `--ban "glossy 3D rendering"` |
| Gradient text on headings | `--ban "gradient text fills"` |
| Invented gibberish text | `--ban "all invented text and gibberish"` |
| Duplicate logos | `--ban "duplicate logo marks"` |
| Decorative unreadable text | `--ban "decorative unreadable text"` |
| Cards nested inside cards | `--ban "nested card containers"` |

**Decision rule:**

- **Mean score < 3 → ITERATE.** Record rejection, re-generate with corrections:
  ```bash
  source .venv/bin/activate && bgen feedback <version> --score <N> --notes "<issues>" --status rejected
  source .venv/bin/activate && bgen pipeline --material-type <type> --source-version <version> \
    --ban "<defect>" --push "<improvement>" --max-iterations 2 --format json
  ```
  Max 2 retry cycles.

- **Mean score >= 3 → ACCEPT.** Record feedback:
  ```bash
  source .venv/bin/activate && bgen feedback <version> --score <N> --notes "<summary>"
  ```

**Always ask the user for their score after the agent critique.** Present the output
and ask: "I scored this [N]/5. What's your score? (1-5, or skip to accept mine)."
The user's score ALWAYS overrides the agent's score.

### Phase 6: Evolve

Extract patterns for future runs. Full details:
[references/phase-6-evolve.md](references/phase-6-evolve.md)

```bash
source .venv/bin/activate && bgen evolve --format json
```

**Auto-evolve trigger:** Run evolve automatically when 5+ versions have been scored
since the last evolve run. Track the last evolve timestamp in iteration memory.

Record new model/mode preferences so Phase 1 reads them on the next run. This is
how the pipeline compounds — each run teaches the next one.

---

## Decision Rules

These rules govern choices throughout the pipeline:

### Mode Selection
1. Check learnings first. If a winning setup exists for this material type, use it.
2. Otherwise default to `hybrid`.
3. Trust learnings over material defaults. Do not second-guess recorded wins.

### When to Iterate
- Mean critique score < 3
- Specific P1 issues: wrong palette, invented text, broken composition
- AI slop anti-patterns detected
- User scores below 3

### When to Stop
- Mean score >= 3 AND no P1 issues
- 2 retry cycles exhausted — report final result with honest assessment
- User explicitly accepts

### When to Create a Philosophy
- `design-philosophy.md` does not exist for the active brand
- See [references/philosophy-workflow.md](references/philosophy-workflow.md) for the
  full creation workflow

### When to Run Competitive Research
- Material type has no `modelPreferences` in learnings AND fewer than 3 scored versions
- See the competitive research section in
  [references/philosophy-workflow.md](references/philosophy-workflow.md)

### Vault Sync Cadence
- Every 10 generations, or on first run
- Check `.brand-gen-local.json` → `vault_paths` for configured vault directories
- Compare vault file mtimes against last sync timestamp in iteration memory

---

## Output Format

Return structured JSON on completion:

```json
{
  "status": "completed|iterated|max_retries_exhausted",
  "final_version": "v048",
  "total_iterations": 1,
  "final_score": 4.0,
  "preparation_insights": {
    "learnings_applied": ["[social] Winning setup: hybrid + html:chromium"],
    "layout_suggestion": "compact_proof_card",
    "role_pack": "composition references available",
    "concept_selected": "governance/curation",
    "philosophy_applied": true
  },
  "versions_generated": [
    {"version": "v048", "score": 4, "status": "accepted"}
  ],
  "image_paths": ["/path/to/final/image.png"],
  "learnings_extracted": ["concept illustrations benefit from particle-convergence mechanic"]
}
```

---

## Inputs

The pipeline accepts these inputs from the caller:

| Input | Required | Description |
|-------|----------|-------------|
| `material_type` | Yes | e.g. brand-scene, concept-illustration, social, campaign-poster |
| `prompt_seed` | No | Creative direction seed text |
| `purpose` | No | What job this material does |
| `target_surface` | No | Where it appears (social feed, website hero, pitch deck) |
| `product_truth` | No | Concrete product truth to express |
| `mode` | No | reference, inspiration, or hybrid (default: from learnings) |
| `preserve` | No | Elements to keep from a previous version |
| `push` | No | Elements to amplify |
| `ban` | No | Elements to prohibit |

---

## Reference Files

Load these as needed for full procedural details. Each covers one pipeline phase:

| File | Contents | When to read |
|------|----------|-------------|
| [phase-1-prepare.md](references/phase-1-prepare.md) | Creative context bootstrap, vault sync, philosophy check, learnings, role pack, layout, copy ideation, concept diversity, base image, logo resolution | Before first generation or when preparation details are unclear |
| [phase-2-plan.md](references/phase-2-plan.md) | Route selection, plan-draft creation, philosophy enrichment, preserve/push/ban flags | When building the plan |
| [phase-3-validate.md](references/phase-3-validate.md) | Structural critique, brand-fit validation, P3-to-blocker promotions, design coherence matrix | When validation fails or edge cases arise |
| [phase-4-generate.md](references/phase-4-generate.md) | Scratchpad building, generation flags, base image handling, blocking issues | When generation has problems |
| [phase-5-critique.md](references/phase-5-critique.md) | Full scoring rubric, AI slop anti-pattern list, ban/push directive format, user feedback flow | When scoring or iterating |
| [phase-6-evolve.md](references/phase-6-evolve.md) | Pattern extraction, auto-evolve triggers, learnings format | After generation cycles |
| [philosophy-workflow.md](references/philosophy-workflow.md) | Philosophy creation, refinement, competitive research | When design-philosophy.md is missing or stale |

---

## What to Avoid

0. **Never manually edit `custom-scratchpad.json`, `custom-scratchpad.md`, `learnings.json`, `iteration-memory.json`, or `brand-identity.json`** — use the typed mutation verbs from the "Typed runtime" section above (`bgen append-forbidden-pattern`, `bgen append-custom-scratchpad-note`, `bgen promote-learning`, `bgen promote-style-policy`, `bgen update-palette`, `bgen update-typography`, `bgen update-devices`, `bgen set-motion-grammar`, `bgen submit-review`). Direct edits bypass the run ledger and corrupt agent-vs-user disagreement capture.

0b. **Never default to `bgen pipeline` when `bgen orchestrate-material` works.** Pipeline is a CI/scripting fallback; orchestrate-material is the primary path with typed `{stop_reason, next_action, artifacts}` response shape.

1. **Never skip preparation.** Phase 1 prevents repeating known failures and ensures
   concept diversity. Skipping it wastes generation budget on problems already solved.

2. **Never generate from an unvalidated plan.** Phase 3 catches model-text mismatches,
   brand-fit violations, and mode issues for free. Generation costs real money.

3. **Never paste the design philosophy verbatim into prompts.** Extract its essence —
   material words, composition rules, quality boosters. Verbatim philosophy produces
   overwrought, self-referential output.

4. **Never ignore learnings.** If learnings say a mode wins for a material type, use
   it. Overriding recorded wins without evidence wastes iterations.

5. **Never give vague iteration feedback.** "Make it better" does not help. Specify
   what is wrong and provide concrete `--ban` and `--push` directives.

6. **Never silently accept AI slop.** The anti-pattern checklist exists because image
   models default to these patterns. Every slop tell must produce a ban directive.

7. **Never override the user's score.** The agent critique is a starting point. The
   user's score is final.

8. **Never hardcode brand-specific content.** All palette, typography, and identity
   data comes from `brand-profile.json` and `brand-identity.json`. All machine paths
   come from `.brand-gen-local.json`. All quality benchmarks come from
   `creative_context.quality_benchmarks`.

9. **Never exceed 2 retry cycles.** If the output is still below the bar after 2
   iterations, report honestly and move on. Diminishing returns are real.

10. **Never forget to record feedback.** Every generated version needs a score in the
    system. Unscored versions are invisible to the learning loop.

---

## Quick Reference: Key File Locations

All paths are relative to `.brand-gen/brands/<active>/`:

| File | Purpose |
|------|---------|
| `brand-profile.json` | Core brand data, creative context, design language |
| `brand-identity.json` | Computed identity summary |
| `design-philosophy.md` | Named aesthetic movement |
| `learnings.json` | Winning model/mode setups, failure patterns |
| `iteration-memory.json` | Notes, positive/negative examples, vault sync timestamps |
| `manifest.json` | All generated versions with metadata and feedback |
| `blackboard.json` | Active brief, decisions, lineage |
| `scratchpads/` | Plan drafts, critiques, generation scratchpads |

Machine config: `.brand-gen-local.json` (repo root — vault paths, repo root path)
Runtime config: `.brand-gen/config.json` (active brand, session state)
