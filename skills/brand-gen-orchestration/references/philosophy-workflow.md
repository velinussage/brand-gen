# Philosophy Workflow

## Table of Contents

1. [When to Create a Philosophy](#when-to-create-a-philosophy)
2. [Data Sources](#data-sources)
3. [First Creation Workflow](#first-creation-workflow)
4. [Refinement Workflow](#refinement-workflow)
5. [Philosophy Output Format](#philosophy-output-format)
6. [Competitive Research](#competitive-research)

---

## When to Create a Philosophy

A design philosophy is a named aesthetic movement — a poetic, opinionated worldview
distilled from existing brand thinking. It is discovered in the language a brand already
uses, not invented from scratch.

**Create when:**
- `design-philosophy.md` does not exist for the active brand (Phase 1 check)
- The brand has source material to work from (vault, brand identity, inspiration)

**Refine when:**
- Vault content has been updated since the philosophy was written
- Recent `philosophy_fit` scores are consistently low
- The user expresses preferences not captured in the philosophy

**Skip creation when:**
- No source material exists at all (no vault, no brand identity beyond basics)
- In this case, proceed without a philosophy and let generation results inform a
  future philosophy creation

---

## Data Sources

Read these in order. Each source type contributes different intelligence:

### 1. Brand Vault (Primary — The Soul)

Read vault paths from `.brand-gen-local.json` → `vault_paths`. If no vault is
configured, the philosophy can still be synthesized from other sources.

If vault paths exist, recursively scan for `.md` files and read them in order of
modification date (newest first). Look for content about:
- Metaphors and symbols
- Emotional territory
- Design language and principles
- Aspirational brands
- Brand tensions (opposing forces that make the brand interesting)
- Core values
- Voice and positioning

**Do not skim vault files.** Read them fully. The philosophy is already in there —
scattered across metaphors, emotional territory, and design principles.

### 2. Brand Identity JSON (Secondary — The Mechanics)

```bash
source .venv/bin/activate && bgen context-snapshot --format json
```

Read for:
- Palette direction and what materials the colors evoke
- Typography choices and what voice the fonts carry
- Tone words
- Approved graphic devices and forbidden elements

### 3. Inspiration Sources (Tertiary — External Influences)

```bash
ls .brand-gen/inspiration/*/
```

Read `.design-memory` files from configured inspiration sources to understand the
aesthetic landscape the brand operates in.

### 4. Generation History (For Refinement)

```bash
source .venv/bin/activate && bgen show --format json --latest 10
source .venv/bin/activate && bgen show-iteration-memory --format json
```

Read scored outputs and iteration notes:
- What scored highest? What aesthetic qualities does the best work share?
- What scored lowest? What went wrong?
- Are there negative examples that reveal what the philosophy should exclude?

### 5. Quality Benchmarks

Read `brand-profile.json` → `creative_context.quality_benchmarks`. Use these as
calibration points when reading vault content about aspirational brands.

---

## First Creation Workflow

### Step 1: Deep Reading (30% of effort)

Read ALL vault sources. Take notes on:
- **Recurring metaphors** — What images keep appearing?
- **Emotional register** — What should the work feel like?
- **Design principles** — What rules exist already?
- **Tensions to hold** — What opposing forces make the brand interesting?
- **What the brand is NOT** — Often more revealing than what it is

### Step 2: Synthesis (20% of effort)

Find the through-line. The vault will contain many metaphors, emotional registers,
and design principles. The philosophy must find the ONE aesthetic movement that holds
all of them.

Look for convergence:
- If "institutional weight" AND "natural materials" AND "quiet authority" → the
  movement might live at the intersection of architecture and earth
- If "curation" AND "wardrobe" AND "gallery" → the movement is about deliberate
  selection made visible
- If "craftsmanship" AND "rigor" AND "four rounds of review" → the movement
  demands visible rigor

### Step 3: Ask the User (10% of effort)

Before writing, ask 1-3 targeted questions. Examples:
- "The vault describes [X] and [Y] as core metaphors. Which feels more central to
  how you see the brand visually?"
- "The emotional territory emphasizes quiet authority. Should the philosophy lean
  toward institutional gravitas or organic warmth?"
- "The quality benchmarks include [list]. Which end of that spectrum feels more
  like the brand's visual future?"

Do NOT ask generic questions. Every question must reference specific source content.

### Step 4: Name the Movement

The name should:
- Capture the central tension or metaphor
- Feel like an art movement, not a tagline
- Be specific enough that another brand could not use it
- Be evocative enough to inspire diverse material types

**Good:** "Structural Reverence", "Cultivated Geology"
**Bad:** "Modern Clean", "Bold Minimal", "Premium Design"

### Step 5: Write the Philosophy

4-6 paragraphs covering distinct dimensions:
- Each paragraph references specific vault content (transformed, not copied)
- Describe feelings and materials, not specs (no hex codes, no font names)
- Include craftsmanship language at least 3 times across the philosophy
- Leave room for interpretation across material types

### Step 6: Humanizer Pass

Review for AI writing patterns:
- Remove promotional language ("vibrant", "stunning", "cutting-edge")
- Remove significance inflation ("pivotal", "transformative", "revolutionary")
- Vary sentence rhythm — mix short declarative with longer flowing
- Have opinions — the philosophy should feel authored, not generated
- Use specific material references over abstract adjectives

### Step 7: Save

Save to `.brand-gen/brands/<active>/design-philosophy.md`

---

## Refinement Workflow

When the philosophy exists but may need updating:

### Check for Drift

1. **New vault content?**
   ```bash
   find "<vault_path>" -newer .brand-gen/brands/<active>/design-philosophy.md -name "*.md" 2>/dev/null
   ```

2. **Generation feedback?** Check iteration memory for low `philosophy_fit` scores.
   If multiple outputs score below 3 on philosophy_fit, the philosophy may need
   sharpening.

3. **High-scoring outliers?** If outputs that score 4-5 share qualities not in the
   philosophy, it may need expanding.

4. **User feedback?** Has the user expressed preferences the philosophy does not
   capture?

### Propose, Do Not Overwrite

Present specific proposed changes:
- "Based on [new vault content], I'd suggest adding [X] to the philosophy"
- "Recent low philosophy_fit scores suggest [Y] isn't guiding well — adjust?"
- "The vault now includes [Z] which isn't reflected"

Only update after user confirmation. The user owns the philosophy.

---

## Philosophy Output Format

After creating or refining a philosophy, extract these for immediate use in Phase 2:

```json
{
  "movement_name": "Structural Reverence",
  "prompt_translation_hints": {
    "material_words": ["rammed earth", "aged stone", "warm parchment", "fired clay"],
    "composition_rules": ["one dominant gesture", "architectural rhythm", "weight at the base"],
    "quality_boosters": ["meticulous", "master-level", "deliberately placed", "labored over"]
  }
}
```

These three lists are the bridge between the poetic philosophy and the concrete
prompt engineering of Phase 2.

---

## Competitive Research

**Why:** When the pipeline encounters a material type with no learnings (cold start),
competitive research establishes a visual baseline so the first generation is informed
rather than blind.

### Trigger Conditions

Run competitive research when ALL of these are true:
1. Material type has no `modelPreferences` entry in `learnings.json`
2. Fewer than 3 versions of this material type exist in the manifest
3. This is genuinely a new category for the brand

### Step 1: Identify the Category Landscape

Search for best-in-class examples. Run 2-3 web searches:
- "best [material_type] design [brand_industry] 2025 2026"
- "[material_type] design inspiration premium brands"
- "award winning [material_type] [brand_industry]"

Infer the brand's industry from `brand-profile.json` → `description` and `keywords`.

### Step 2: Analyze Top Results (3-5 sources)

For each top result, extract:
- **Composition patterns** — asymmetric, centered, split, grid
- **Color approach** — restrained or expressive, dark or light dominant
- **Typography treatment** — display fonts, weight contrast, scale hierarchy
- **Density/whitespace** — packed or airy
- **What makes the best ones stand out** from the generic ones

### Step 3: Write a Research Brief

```markdown
## Material Research: [material_type]

### Category Baseline (what users expect)
- [2-3 table-stakes patterns]

### Opportunities (where the brand can stand out)
- [2-3 departures from convention]

### Composition Recommendations
- Preferred layout, focal hierarchy, density

### Model/Mode Recommendation
- Suggested model + mode with rationale

### Sources
- [URL] — [what was useful]
```

### Step 4: Store Findings

Save to `.brand-gen/brands/<active>/material-research/<material_type>-research.md`

### Step 5: Feed Into Planning

When creating a plan for a researched material type:
- Baseline patterns → `--preserve` (output should feel literate in its category)
- Opportunity patterns → `--push` (output should stand out)
- Model/mode recommendation → `--mode` and model selection

### Research Rules

1. Research is discovery, not copying. Extract patterns, not designs.
2. Always identify both baseline AND opportunity.
3. Be specific about what makes the best examples good. "Clean design" is useless.
   "High weight-contrast between display and body type creates clear scan hierarchy"
   is useful.
4. Store findings persistently — research only runs once per material type unless
   the user asks for a refresh.
5. Brand identity and philosophy always take precedence over category conventions.
6. Time-box: 3-5 sources maximum. Do not over-research.
