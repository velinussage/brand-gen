# Phase 1: Prepare

## Table of Contents

1. [Explorer Pass](#explorer-pass)
2. [Creative-Context Bootstrap](#creative-context-bootstrap)
3. [Vault Sync](#vault-sync)
4. [Design Philosophy Check](#design-philosophy-check)
5. [Learnings Check](#learnings-check)
6. [Blackboard Check](#blackboard-check)
7. [Role Pack Suggestion](#role-pack-suggestion)
8. [Layout Suggestion](#layout-suggestion)
9. [Improvement Questions](#improvement-questions)
10. [Copy Ideation](#copy-ideation)
11. [Concept Diversity Check](#concept-diversity-check)
12. [Base Image Check](#base-image-check)
13. [Logo Resolution](#logo-resolution)

---

## Explorer Pass

**Why:** The Pi-style workflow starts with a read-only workspace inspection. Without it,
planning drifts into generic prompts instead of building on the actual brand memory.

Before any planning, inspect:

```bash
source .venv/bin/activate && bgen context-snapshot --format json
source .venv/bin/activate && bgen show --format json --latest 10
source .venv/bin/activate && bgen show-blackboard --format json
```

Also inspect at least **2 relevant prior approved / high-scoring versions** and their image files.

Your explorer summary must identify:
- what worked in prior approved outputs
- what failed in prior rejected outputs
- which mechanics are locked
- which variable is safe to change this run

Do not move on to planning until this summary is concrete.

## Creative-Context Bootstrap

**Why:** The `creative_context` block in `brand-profile.json` drives concept diversity
and quality calibration. Older brands created before this block existed will not have it.
Self-healing prevents silent failures downstream.

Read `brand-profile.json` for the active brand. Check if `creative_context` exists.

If missing, do **not** silently overwrite a saved brand workspace during orchestration.
Use these defaults ephemerally for planning:

```json
{
  "creative_context": {
    "quality_benchmarks": ["Stripe", "Aesop", "Criterion", "Muji"],
    "concept_categories": [],
    "metaphor_vocabulary": []
  }
}
```

- `quality_benchmarks`: Read from `.brand-gen-local.json` → `quality_benchmarks` first.
  If not present, use the defaults above.
- `concept_categories`: Copy from `brand-profile.json` → `keywords`. If no keywords
  exist, leave empty.
- `metaphor_vocabulary`: Start empty. The philosophy workflow populates this later.

Only write the new block back to `brand-profile.json` when:
- the user explicitly approved the repair, or
- you are in a disposable testing session.

Otherwise, note in the memo that `creative_context` is missing and continue with ephemeral defaults.

This is a hard rule: do not rewrite an existing saved-brand profile in place during normal orchestration just because schema drift was detected.

---

## Vault Sync

**Why:** Brand vaults (Obsidian, markdown docs) contain the brand's evolving thinking.
Syncing pulls new metaphors, positioning changes, and emotional territory into the
generation pipeline. Without syncing, old generations diverge from current brand thinking.

**Trigger:** Run on first generation, then every 10 generations. Track the last sync
timestamp in iteration memory (look for notes starting with `VAULT_SYNC:`).

Check the manifest version count:
```bash
source .venv/bin/activate && bgen show --format json --latest 1
```

Read vault paths:
```bash
cat .brand-gen-local.json
```

Look for the `vault_paths` array. If `.brand-gen-local.json` does not exist, create it:
```json
{
  "repo_root": "<detected from working directory>",
  "vault_paths": []
}
```
Then ask the user if they have a brand vault to connect.

If vault paths are configured:
1. Read ALL `.md` files from configured vault paths
2. Compare with existing brand notes in iteration memory
3. If new content exists (check file modification times), extract:
   - New metaphors
   - Taglines and emotional territory
   - Positioning shifts
4. Propose specific additions to the user before updating iteration memory
5. Record the sync:
   ```bash
   source .venv/bin/activate && bgen update-iteration-memory \
     --kind brand --note "VAULT_SYNC: <ISO-timestamp>"
   ```

---

## Design Philosophy Check

**Why:** The design philosophy is the creative DNA for all generation. Without it, output
is technically competent but visually anonymous — any brand could have produced it.

Read the philosophy file:
```bash
cat .brand-gen/brands/<active>/design-philosophy.md 2>/dev/null
```

**If it does not exist:** This is a critical gap. Create one before proceeding.
See [philosophy-workflow.md](philosophy-workflow.md) for the full creation process.

**If it exists:** Check if it needs refinement:
- Has the vault been updated since the philosophy was written?
  ```bash
  find "<vault_path>" -newer .brand-gen/brands/<active>/design-philosophy.md -name "*.md" 2>/dev/null
  ```
- Do recent scores suggest drift? Check iteration memory for low `philosophy_fit` scores.
- If refinement is needed, propose specific changes to the user before updating.

**In either case**, extract three things for use in Phase 2:

1. **Material metaphors** — concrete material words for prompt seeds
   (e.g., "fired earth", "aged stone", "linen texture")
2. **Composition rules** — structural guidance for preserve/push lists
   (e.g., "one dominant gesture", "architectural rhythm")
3. **Quality boosters** — craftsmanship phrases for prompt suffixes
   (e.g., "meticulous", "labored over", "masterful")

---

## Inspiration-Set Pass

**Why:** Illustration-first work fails when the pipeline reaches planning with only mood-level brand context. The agent must assemble an explicit inspiration set before plan-drafting so the output does not collapse into poster logic, infographic logic, or full-page hero chrome.

Run on **every non-motion run**:
```bash
source .venv/bin/activate && bgen inspiration-status --format json
```

For standalone illustration requests (signals like **"just the illustration"**, **"not the full landing page"**, **"right-side artwork"**, **"standalone illustration"**):
- inspect configured/extracted inspiration before planning even if the final mode will be `reference`
- assemble a minimum set of **3 inspiration sources**
- identify at least:
  - **1 composition / spatial reference**
  - **1 narrative-system reference**
  - **1 rendering / finish reference**
- write down what each source contributes; do not treat them as an undifferentiated moodboard

If the set is missing, weak, or only contains page-adjacent/full-hero references, **stop** and report the gap. Do not continue with generic planning.

## Learnings Check

**Why:** Learnings encode hard-won knowledge about what works. A winning setup recorded
after 10 generations should not be overridden by default heuristics.

Read learnings directly:
```bash
cat .brand-gen/brands/<active>/learnings.json
```

Look for `modelPreferences` entries matching the requested `material_type`. Each entry
contains:
- Winning mode (reference, inspiration, hybrid)
- Winning model
- Whether references help or hurt
- Evidence versions and correction notes

Apply winning setups explicitly. If learnings say "social works best with hybrid +
nano-banana-2 + with refs", use those parameters in Phase 2.

Also check `failurePatterns` — these are things that reliably fail. Apply them as
`--ban` directives in Phase 2.

Also check for `styleReferencePolicies` (or equivalent style-lock records if your brand memory
stores them elsewhere). These capture cases where a specific prior version must remain the
style anchor even when the concept changes.

Example style-lock:

```json
{
  "material_type": "campaign_poster",
  "required_style_reference_versions": ["v014"],
  "reference_policy": "single_style_anchor",
  "failure_mode_if_missing": "style drift",
  "model_behavior_note": "nano-banana-2 drifts when concepts change unless v014 remains the style carrier"
}
```

If such a policy exists, record it as a locked planning input.

## Blackboard Check

**Why:** Blackboard is the most compact source of operational brand memory. It tells you
which recipes have won, which mechanics should be preserved, and which material-specific
mistakes should not be repeated.

Read:

```bash
cat .brand-gen/brands/<active>/blackboard.json
```

For the requested material, inspect:
- `learning_summary[material]`
- `material_recipes[material]`
- `active_brief` if it is relevant to the same family of work

Translate the findings into concrete planning inputs:
- successful mechanics → `--preserve`
- underexplored improvements → `--push`
- repeated failure modes → `--ban`
- winning mode/model/reference usage → Phase 2 defaults
- required style-anchor versions → explicit mandatory references in Phase 2

If the intended route is `inspiration`, also verify whether real inspiration sources are configured.
If none are configured, flag that now. Do not wait until generation to discover that the
“inspiration” route has no actual inspiration inputs.

Do not treat blackboard as passive context. Its learnings must appear explicitly in the plan.

---

## Role Pack Suggestion

**Why:** Role packs provide composition references — real examples of successful layouts
that guide the image model's composition. Without them, composition is left to chance.

```bash
source .venv/bin/activate && bgen suggest-role-pack --material-type <type> --format json
```

The output includes available composition reference sources. Note them for use as
`--pick composition=<source>` in Phase 2.

---

## Layout Suggestion

**Why:** Different material types benefit from different layout strategies. A social post
needs compact hierarchy; a campaign poster needs dramatic whitespace.

```bash
source .venv/bin/activate && bgen suggest-layout --material-type <type> --format json
```

The output includes layout candidates with design-variance scores. Use the suggested
`--design-variance` value in Phase 2.

---

## Improvement Questions

**Why:** Surfaces gaps in the current brand setup that could improve generation quality.

```bash
source .venv/bin/activate && bgen improvement-questions --format json
```

Review the questions. If any can be answered from existing context (vault, brand profile),
answer them. If they require user input, present the most important 1-2 to the user.

---

## Copy Ideation

**Why:** Text-bearing materials (social posts, announcement cards, campaign posters with
headlines) need copy. Generating copy alongside the visual plan ensures text and image
work together rather than fighting each other.

Only run for materials that include text. Skip for pure visual materials like
concept-illustration, brand-scene, or pattern-system.

```bash
source .venv/bin/activate && bgen ideate-copy \
  --material-type <type> \
  --goal "<what the material should communicate>" \
  --format json
```

The output includes headline, subhead, and CTA candidates. Feed the best options into
Phase 2 via `--headline`, `--subhead`, `--cta` flags.

---

## Concept Diversity Check

**Why:** Without diversity enforcement, generation converges on the same 2-3 concepts
repeatedly. This makes brand materials feel repetitive and limits the brand's visual
vocabulary.

Read concept categories from `brand-profile.json` → `creative_context.concept_categories`.
If empty, derive from `brand-profile.json` → `keywords`. If neither exists, skip.

Read recent generations:
```bash
source .venv/bin/activate && bgen show --format json --latest 30
```

Categorize recent generations by concept. Count occurrences per category.

**If the caller did NOT specify a concept:** Automatically pick the LEAST illustrated
concept. This ensures coverage across the brand's concept space.

**If the caller specified a concept with 3+ existing illustrations:** Flag it:
"This concept has been illustrated N times. Consider [underexplored concept] instead?"

Also check `creative_context.metaphor_vocabulary`. If metaphors are configured, check
iteration memory — are there metaphors that have never been illustrated? Prioritize those.

Also review prior approved implementations. If a concept has already produced a strong
approved mechanic, preserve that mechanic and vary only one dimension at a time.

---

## Base Image Check

**Illustration-only exception:** if the user asked for artwork that will later sit on a landing page, but explicitly said they do **not** want the full page, do **not** use an interface material merely to justify `--base-image`. In that case screenshots are truth-source references, not page-layout scaffolding.

**Why:** Interface materials require a real product screenshot as a base image. Without
one, image models invent fake UI that is immediately recognizable as artificial and
scores 1-2 out of 5 every time.

**Applies to:** `browser-illustration`, `landing-hero`, `product-banner`,
`feature-illustration`

Check if product screenshots exist:
```bash
ls .brand-gen/brands/<active>/product-shots/ 2>/dev/null
```

If screenshots exist, select the one most relevant to the material purpose. Store its
path for use in Phase 2 (`--base-image`) and Phase 4 (`--base-image`).

If NO screenshots exist, capture them:
```bash
source .venv/bin/activate && bgen capture-product \
  --url <app-url> \
  --out-dir .brand-gen/brands/<active>/product-shots
```

The `--base-image` flag is MANDATORY for these material types. Never proceed to Phase 2
without it.

---

## Logo Resolution

**Why:** The brand logo is a brand anchor, not a universal opening frame. The pipeline
auto-injects brand assets after product-truth references for `bgen pipeline` and
`bgen build-generation-scratchpad`, but direct `generate.py` calls must preserve the
same ordering discipline.

Resolve the logo path:
1. Check `.brand-gen/brands/<active>/logo.png` (local workspace copy)
2. Fall back to `brand_assets.icon` in `brand-identity.json`, resolved via `project_root`

Store the resolved absolute path. When calling `bgen image` directly, include
`-i <logo-path>` as a secondary brand reference when the model supports multiple refs.
For non-logo motion (`feature-animation`, `stinger-animation`, `bumper-animation`,
`landing-hero`, `motion-loop`, `short-video`), the first/start-frame reference must be
a product, workflow, capability, or source-still proof. Do **not** pass the logo as the
sole video reference unless the requested material is explicitly `logo-animation`.

---

## Preparation Summary

After completing all steps, collect:

| Insight | Source | Used in |
|---------|--------|---------|
| Material metaphors | Design philosophy | Phase 2 prompt seed |
| Composition rules | Design philosophy | Phase 2 preserve/push |
| Quality boosters | Design philosophy | Phase 2 prompt suffix |
| Winning mode/model | Learnings | Phase 2 --mode, model selection |
| Failure bans | Learnings | Phase 2 --ban |
| Role pack references | suggest-role-pack | Phase 2 --pick |
| Layout strategy | suggest-layout | Phase 2 --design-variance |
| Copy candidates | ideate-copy | Phase 2 --headline/--subhead/--cta |
| Selected concept | Concept diversity | Phase 2 prompt seed |
| Base image path | product-shots/ | Phase 2 + Phase 4 --base-image |
| Logo path | brand assets | All generation commands |
