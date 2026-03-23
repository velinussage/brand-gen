# Phase 5: Critique

## Table of Contents

1. [View the Output](#view-the-output)
2. [Get the Critique Rubric](#get-the-critique-rubric)
3. [Scoring Rubric](#scoring-rubric)
4. [Quality Calibration](#quality-calibration)
5. [AI Slop Check](#ai-slop-check)
6. [Decision Rule](#decision-rule)
7. [Recording Feedback](#recording-feedback)
8. [User Score Override](#user-score-override)
9. [Iteration Directives](#iteration-directives)
10. [Critique Output Format](#critique-output-format)

---

## View the Output

**Why:** Critique requires actually seeing the image. Do not score based on metadata
alone.

Inspect the generated image at the path returned by Phase 4. If your host supports
image viewing (most do), view the image directly. If not, note that the scoring will
rely on the VLM critique from the generation step.

---

## Get the Critique Rubric

```bash
source .venv/bin/activate && bgen critique-rubric <version-id> --format json
```

This returns:
- Image path for inspection
- Material type and intended purpose
- Brand identity context for calibration
- Any plan warnings that were noted during validation

---

## Scoring Rubric

Score each axis from 1 (reject) to 5 (ship-ready):

### Composition (1-5)

| Score | Criteria |
|-------|----------|
| 1 | No hierarchy, competing focal points, unbalanced |
| 2 | Weak hierarchy, elements fight for attention |
| 3 | Clear focal point, adequate whitespace, functional layout |
| 4 | Strong hierarchy, intentional rhythm, editorial quality |
| 5 | Masterful composition — every element precisely placed, breathing room feels deliberate |

### Material Truth (1-5)

| Score | Criteria |
|-------|----------|
| 1 | Wrong material type entirely, does not serve the intended purpose |
| 2 | Recognizable as the type but would not work in context (wrong size, wrong tone) |
| 3 | Functional for the surface, communicates the core message |
| 4 | Strong fit — someone would actually use this in the intended context |
| 5 | Perfectly crafted for its surface and purpose, sets the standard |

### Brand Coherence (1-5)

| Score | Criteria |
|-------|----------|
| 1 | Wrong palette, unauthorized motifs, could be any brand |
| 2 | Palette approximate but off, some brand elements present |
| 3 | Correct palette, logo present, recognizably this brand |
| 4 | Palette precise, motifs approved, strong brand voice |
| 5 | Unmistakably this brand — every choice reinforces identity |

### Restraint (1-5)

| Score | Criteria |
|-------|----------|
| 1 | Invented text, off-brand decoration, generic stock feel, cluttered |
| 2 | Some invented elements, unnecessary decoration |
| 3 | Clean execution, no major inventions, adequate restraint |
| 4 | Disciplined — nothing extraneous, every element earns its place |
| 5 | Zen-like restraint — maximum impact from minimum elements |

### Philosophy Fit (1-5)

| Score | Criteria |
|-------|----------|
| 1 | No connection to the design philosophy, generic aesthetic |
| 2 | Vaguely aligned but could be any brand in the category |
| 3 | Recognizable aesthetic direction, some philosophy elements present |
| 4 | Clearly from the named movement, philosophy principles visible |
| 5 | A definitive expression of the movement — would be included in the manifesto |

---

## Quality Calibration

**Why:** Scores must be calibrated against an external standard, not internal
satisfaction. A 4/5 should hold up next to the aspirational brands, not just
look better than yesterday's output.

Read `brand-profile.json` → `creative_context.quality_benchmarks`. Defaults:
`["Stripe", "Aesop", "Criterion", "Muji"]`

For each score, ask: "Would this hold up next to similar material from these brands?"
If no, the score is probably too high.

Also calibrate against the design philosophy. A technically excellent output that
feels generic (any brand could have made it) should score low on philosophy_fit
even if other axes are high.

---

## AI Slop Check

**Why:** Image models have default aesthetics — patterns they fall into when the prompt
is not specific enough. These patterns are immediately recognizable as AI-generated and
undermine brand credibility.

Scan the output for these anti-patterns. Any match is an automatic P1 issue with a
specific ban directive for iteration.

### Visual Anti-Patterns (auto-P1)

| Pattern | What to look for | Ban directive |
|---------|-----------------|---------------|
| Purple/violet gradients | Purple-to-blue gradient backgrounds or overlays | `"purple gradients"` |
| Cyan-on-dark neon | Neon cyan or electric blue accents on dark backgrounds | `"neon cyan accents on dark background"` |
| Glassmorphism | Frosted glass panels, blur effects, translucent cards | `"glassmorphism, frosted glass panels"` |
| 3-column icon grid | Three columns of icons with colored circles behind them | `"3-column icon grid with colored circles"` |
| Glossy 3D | Glossy, plastic-looking 3D renders when the brief says flat | `"glossy 3D rendering"` |
| Gradient text | Gradient fills on heading text | `"gradient text fills"` |

### Typography Anti-Patterns (auto-P1)

| Pattern | What to look for | Ban directive |
|---------|-----------------|---------------|
| Gibberish text | Invented words, lorem ipsum, garbled characters | `"all invented text and gibberish"` |
| Duplicate logos | Brand mark appears more than once | `"duplicate logo marks"` |
| Decorative text | Unreadable text used as decoration | `"decorative unreadable text"` |

### Composition Anti-Patterns (auto-P2)

| Pattern | What to look for | Push directive |
|---------|-----------------|---------------|
| Centered everything | All elements centered with uniform spacing | `"asymmetric editorial layout"` |
| Nested cards | Cards inside cards, multiple container layers | `"nested card containers"` (ban) |

---

## Decision Rule

Compute the mean score across all 5 axes.

### Mean < 3 → ITERATE

The output does not meet the quality bar. Record rejection and iterate:

1. Record the rejection:
   ```bash
   source .venv/bin/activate && bgen feedback <version-id> \
     --score <mean-score> \
     --notes "<specific issues, comma-separated>" \
     --status rejected
   ```

2. Construct ban and push directives from the critique findings

3. Re-generate:
   ```bash
   source .venv/bin/activate && bgen pipeline \
     --material-type <type> \
     --source-version <version-id> \
     --ban "<defect-1>" --ban "<defect-2>" \
     --push "<improvement-1>" --push "<improvement-2>" \
     --max-iterations 2 \
     --format json
   ```

4. Critique the new output (return to the start of Phase 5)
5. Maximum 2 retry cycles total

### Mean >= 3 → ACCEPT

The output meets the quality bar. Record acceptance:

```bash
source .venv/bin/activate && bgen feedback <version-id> \
  --score <mean-score> \
  --notes "<summary of strengths and minor issues>"
```

If the score is 4+, also note in iteration memory what worked — this feeds Phase 6.

### Edge Cases

- **Score of exactly 3 with P1 issues:** ITERATE. P1 issues override the mean threshold.
- **Score of 4+ with AI slop detected:** ITERATE. Slop is an automatic rejection
  regardless of other scores. The ban directives will fix it on the next attempt.
- **2 retry cycles exhausted, still below 3:** STOP. Report the best version achieved
  with an honest assessment: "Best attempt scored [N]/5 after 2 iterations. Key
  remaining issues: [list]."

---

## Recording Feedback

**Why:** Every generated version must have a score in the system. Unscored versions are
invisible to the learning loop — they cannot contribute to model preferences, failure
patterns, or composition patterns in `learnings.json`.

```bash
source .venv/bin/activate && bgen feedback <version-id> \
  --score <1-5> \
  --notes "<description>" \
  [--status rejected|favorite]
```

- `--status rejected` for scores 1-2 or any output with P1 issues
- `--status favorite` for scores 4-5 that represent the brand's best work
- Omit `--status` for scores of 3 (acceptable but not remarkable)

---

## User Score Override

**Why:** The agent critique is a starting point, not the final word. The user
understands brand intent better than any scoring rubric.

After completing the agent critique, ALWAYS present the output to the user:

```
I scored this [N]/5. What's your score? (1-5, or skip to accept mine)
```

If the user provides a different score:

```bash
source .venv/bin/activate && bgen feedback <version-id> \
  --score <user-score> \
  --notes "<user's feedback>"
```

The user's score ALWAYS overrides the agent's score. Record any specific feedback
as positive or negative examples in iteration memory:

```bash
source .venv/bin/activate && bgen update-iteration-memory \
  --kind <positive|negative> \
  --version <version-id> \
  --note "<user's specific feedback>"
```

---

## Iteration Directives

When returning ITERATE, construct directives specific enough to use as CLI flags:

**Ban directives** (things to remove):
- Must name the specific defect: `"purple gradients"` not `"bad colors"`
- Must be concrete enough for an image model to understand
- One ban per defect — do not combine multiple issues

**Push directives** (things to amplify):
- Must name the specific improvement: `"asymmetric editorial layout"` not `"better layout"`
- Should address the specific axis that scored lowest
- Should reference preparation context (philosophy, learnings) when possible

---

## Critique Output Format

```json
{
  "decision": "ITERATE|ACCEPT",
  "mean_score": 2.4,
  "scores": {
    "composition": 3,
    "material_truth": 2,
    "brand_coherence": 3,
    "restraint": 2,
    "philosophy_fit": 2
  },
  "p1": ["Invented gibberish text in the lower third"],
  "p2": ["Composition is centered with uniform spacing"],
  "slop_detected": ["gradient text fills", "glossy 3D rendering"],
  "iteration_directives": {
    "ban": ["gradient text fills", "glossy 3D rendering", "all invented text"],
    "push": ["asymmetric editorial layout", "natural material textures"],
    "prompt_seed_update": "..."
  },
  "summary": "Output shows competent layout but defaults to AI aesthetic patterns. Two slop tells detected (gradient text, glossy 3D). Text is invented gibberish. Iterate with ban directives.",
  "feedback_recorded": true
}
```
