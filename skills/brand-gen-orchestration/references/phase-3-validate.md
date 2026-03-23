# Phase 3: Validate

## Table of Contents

1. [Structural Critique](#structural-critique)
2. [Brand-Fit Validation](#brand-fit-validation)
3. [P3-to-Blocker Promotions](#p3-to-blocker-promotions)
4. [Design Coherence Check](#design-coherence-check)
5. [Handling Validation Failures](#handling-validation-failures)

---

## Structural Critique

**Why:** The structural critique catches technical problems in the plan — missing
parameters, contradictory flags, unsupported combinations. These are cheap to fix
before generation and expensive to discover after.

```bash
source .venv/bin/activate && bgen critique-plan --plan <plan-path> --format json
```

The output includes:
- **P1 issues** — Must fix before generating. Concrete defects.
- **P2 issues** — Should fix. May degrade quality.
- **P3 issues** — Advisory. Note but do not block.
- **Blocking flag** — If true, do not proceed.

Read every issue. P1 and P2 issues need specific responses. P3 issues should be noted
for post-generation review.

---

## Brand-Fit Validation

**Why:** A plan can be structurally sound but off-brand. Brand-fit validation checks
alignment with the brand identity — palette direction, approved devices, forbidden
elements, tone words.

```bash
source .venv/bin/activate && bgen validate-brand-fit --plan <plan-path> --format json
```

Add `--strict` for stricter validation (recommended for brand-critical materials like
campaign posters and social posts that represent the brand publicly).

The output includes fit score and specific misalignment notes. A low fit score
(< 0.6) should be treated as blocking.

No generation is allowed before both the structural critique and brand-fit pass are complete.

---

## P3-to-Blocker Promotions

**Why:** Some warnings classified as P3 (advisory) by the automated critique are
actually blocking in practice. These promotions encode hard-won lessons about what
reliably fails.

After reading the critique output, check for these specific P3 warning texts and
promote them to BLOCKING:

### 1. "Exact text request detected"

**Promote to:** BLOCK

**Why it matters:** Image models cannot reliably render specific text. A plan asking
for "Deploy in 60 Seconds" rendered as text in the image will produce gibberish,
misspellings, or garbled characters in the majority of attempts.

**Action:** Return the plan to Phase 2. Tell the planner WHAT is wrong ("the plan
asks an image model to render specific text, which reliably fails") but do NOT
prescribe HOW to fix it. The planner chooses: stronger text model, shorter text
(3 words or fewer), removing text, compositing pipeline, or another approach.

### 2. "hybrid mode has been underperforming"

**Promote to:** BLOCK if the plan still uses hybrid mode

**Why it matters:** If learnings show that hybrid mode underperforms for this material
type, continuing to use it wastes a generation cycle on a setup known to fail.

**Action:** Return to Phase 2. Switch to the winning mode from `learnings.json`.

### 3. "text issues found from prior version"

**Promote to:** BLOCK

**Why it matters:** The previous version already failed on text with the same setup.
Repeating the identical configuration will produce the identical failure.

**Action:** Return to Phase 2. Require the planner to change something — model, mode,
text strategy, or brief scope. Do not repeat a failing configuration.

### All Other P3 Warnings

Remain advisory. Proceed but note them for post-generation review. They may become
relevant if the output scores poorly.

Also check whether the plan still reflects the required evidence base:
- blackboard learnings for the material
- prior approved implementations
- explicit route choice
- explicit preserve / push / ban logic

Promote to BLOCKING when:
- the route claims `inspiration` but `selected_inspiration_ids` is empty and no explicit reroute was recorded
- the plan relies on reference roles for grounding, but the selected model/wrapper will not actually transport those refs into image generation
- a style-lock policy exists for this material, but the required style reference version is not explicitly carried into the plan

If those are absent or too vague, treat the plan as needing revision even if the validator
does not emit a formal blocking flag.

---

## Design Coherence Check

**Why:** A plan can pass structural and brand-fit checks while containing internally
contradictory choices. These contradictions produce output that fights itself — a
text-heavy plan sent to a model that cannot render text, or a vertical composition
on a horizontal canvas.

Run this check on every plan. Flag mismatches as P2 unless noted as P1.

### Model vs. Text Complexity

This is the most important coherence check.

| Text needs | Likely to work | Risky — flag it |
|-----------|---------------|-----------------|
| No text at all | Any model | — |
| Short tagline (3 words or fewer) | flux-2-flex, ideogram | nano-banana-2 (P2) |
| Headline (4+ words) | Needs text-capable approach | Any image-only model without text strategy (P1) |
| Logo with wordmark | ideogram, recraft-v4 | nano-banana-2 (P1) |

If `preserve[]` contains exact text strings and the plan has no clear text rendering
strategy, escalate to P1: "Plan requires exact text but has no text rendering strategy."

### Typography vs. Material Type

- **Text-heavy materials** (campaign poster with copy, social with headline) need a text
  rendering strategy. Flag P2 if none is evident.
- **No-text materials** (concept-illustration, brand-scene, pattern-system) should NOT
  have copy in `preserve[]`. Flag P2 if they do — stray text instructions cause gibberish.

### Color/Contrast vs. Surface

- **Social posts** need high contrast at thumbnail size. Flag low-contrast palette
  combinations as P2. Social posts are often viewed at 150px wide on a phone screen.
- **Campaign posters** need clear hierarchy. Flag more than 3 competing focal elements
  as P2. Posters are glanced at, not studied.

### Composition vs. Aspect Ratio

- **9:16 vertical** needs strong vertical rhythm. Flag horizontal composition direction
  as P2. Elements should stack, not spread.
- **1:1 square** needs centered or radial hierarchy. Flag strongly asymmetric composition
  as advisory. Square formats reward balance.
- **16:9 horizontal** supports asymmetric editorial layouts. Flag overly centered
  compositions as advisory.

---

## Handling Validation Failures

When validation produces BLOCKING issues:

1. Read the blocking reasons carefully
2. Identify which Phase 2 parameters need adjustment (prompt seed, mode, bans, picks)
3. Adjust and rerun `bgen plan-draft` with refinements
4. Re-validate the new plan
5. Maximum 2 plan revision iterations. If still blocking after 2, report the issues
   to the user and ask for direction.

When validation produces warnings only:

1. Note the warnings
2. Proceed to Phase 4
3. After generation, check if any warnings predicted actual quality issues
4. If they did, update the P3-to-blocker promotion list for future runs

Do not bypass validation by switching to ad hoc direct generation or deterministic fallback
unless you explicitly report:
- why the normal pipeline is blocked
- why the fallback matches the requested artifact type
- what brand-truth constraints will still be preserved

### Validation Output Format

The combined validation result should track:

```json
{
  "structural_critique": { "blocking": false, "p1": [], "p2": [], "p3": [] },
  "brand_fit": { "score": 0.85, "misalignments": [] },
  "promoted_blockers": [],
  "coherence_flags": [],
  "decision": "PROCEED|REVISE|BLOCK",
  "revision_count": 0
}
```
