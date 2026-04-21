# Phase 2: Plan

## Table of Contents

1. [Route Selection](#route-selection)
2. [Philosophy Enrichment](#philosophy-enrichment)
3. [Plan-Draft Creation](#plan-draft-creation)
4. [Plan-Draft Flags Reference](#plan-draft-flags-reference)
5. [Plan Review](#plan-review)
6. [Interface Material Planning](#interface-material-planning)

---

## Route Selection

**Why:** Different material requests need different pipeline strategies. A product-truth
illustration needs reference grounding; a pattern system needs generative exploration.
Choosing the wrong route wastes the entire generation cycle.

Run route selection:
```bash
source .venv/bin/activate && bgen route-request \
  --material-type <type> \
  --goal "<what this material should accomplish>" \
  --format json
```

Or skip auto-routing with `--route <route_key>` if the route is already known.

### Route Keys

| Route | When to use | Characteristics |
|-------|------------|-----------------|
| `reference_translate` | Product truth must survive, reference-grounded output | Faithful to source material, controlled composition |
| `generative_explore` | Brand-first exploration, pattern systems, sticker families | Creative freedom, broader concept search |
| `motion_specialist` | Motion or animation work | Motion-specific models and parameters |
| `set_orchestrator` | Multi-asset families or campaign sets | Coordinated output across multiple pieces |

The router returns a `route_key`, `confidence` score, and reasoning. If confidence is
low (< 0.6), consider whether the material request is ambiguous and clarify with the user.

Record the route decision in a compact planning memo. Do not jump from explorer findings
straight into prompt writing without explicitly naming the route and why it fits.

If the route is `inspiration` but there are no configured inspiration sources, do not continue
as if the route is healthy. Either reroute explicitly to a prior-winner / brand-memory plan,
or stop and report the missing inspiration setup.

If the request is illustration-only ("just the illustration", "not the full landing page", "right-side artwork", "standalone illustration"), do **not** let landing-page placement force you into a strict page-scaffold material. The artifact is the artwork, not the page. `feature-illustration` may still be appropriate, but only if you explicitly constrain it as standalone artwork rather than a full page comp.

---

## Philosophy Enrichment

**Why:** The design philosophy provides the creative DNA that makes output distinctively
this brand rather than generically professional. Enrichment translates abstract philosophy
into concrete prompt language.

From Phase 1, you extracted three things from the design philosophy:
- **Material metaphors** (e.g., "fired earth", "aged stone", "linen texture")
- **Composition rules** (e.g., "one dominant gesture plus one support system")
- **Quality boosters** (e.g., "meticulous", "labored over every alignment")

Weave these into the prompt seed:

1. Use material words as texture and quality references in the prompt body
2. Apply composition rules as structural guidance (not literal instructions)
3. End with craftsmanship boosters as quality modifiers

**Do NOT:**
- Paste the philosophy verbatim — this produces overwrought, self-referential output
- Use all metaphors at once — pick 2-3 that fit this specific material
- Force composition rules that contradict the layout suggestion
- Ignore blackboard / prior approved mechanics when they already point to a winning direction
- Treat a landing-page illustration request as permission to generate a full landing page, hero comp, browser mockup, or screenshot-proof inset

**Example transformation:**

Philosophy says: "Every piece should feel like it was made by hand on a surface that
has witnessed weather — stone that remembers rain, earth that holds heat."

Prompt seed becomes: "...textured surface with warmth of sun-baked earth, grain visible
at edges, deliberately placed elements with meticulous attention to negative space"

Also enrich from blackboard and prior winners:
- preserve successful mechanics from approved versions
- explicitly avoid mechanics blackboard flags as failures
- state what is intentionally new versus intentionally locked

---

## Plan-Draft Creation

Build the plan using all preparation context:

```bash
source .venv/bin/activate && bgen plan-draft \
  --material-type <type> \
  --mode <mode from learnings or hybrid> \
  --purpose "<purpose from caller or inferred>" \
  --target-surface "<where this appears>" \
  --prompt-seed "<seed enriched with philosophy>" \
  --abstraction-level <low|medium|high> \
  --design-variance <1-10 from layout suggestion> \
  --format json
```

Add constraint flags from preparation:
- `--preserve "<element to keep>"` (repeatable)
- `--push "<element to amplify>"` (repeatable)
- `--ban "<element to prohibit>"` (repeatable)
- `--pick composition=<source>` (from role pack)

Treat the logo / brand mark as a brand-anchor input, not as a generic semantic role translation problem.
Do not force `logo.png` through a role interpretation that turns it into fake “product truth” like nav structure or button labels.

For illustration-only requests:
- explicitly record `artifact scope = illustration only`
- explicitly record `not the full landing page / not the page itself`
- list the inspiration set in three buckets: `composition`, `narrative/system`, `rendering/style`
- if your selected material is page-adjacent/interface, stop and re-pick before validation

If a style-lock policy exists:
- include the required style reference version(s) explicitly in the plan
- state that they are mandatory style carriers, not optional adjacent winners
- allow other refs to vary for concept/mechanic only after the style anchor is locked
- if the current toolchain has no dedicated `style` role, record the style anchor explicitly in the planning memo and keep it first in the evidence list

### Flags from Preparation

| Preparation insight | Flag | Example |
|--------------------|------|---------|
| Learnings: winning mode | `--mode` | `--mode inspiration` |
| Learnings: failure pattern | `--ban` | `--ban "gradient text"` |
| Philosophy: composition rule | `--preserve` | `--preserve "single dominant focal point"` |
| Role pack: composition ref | `--pick` | `--pick composition=editorial` |
| Layout: variance score | `--design-variance` | `--design-variance 6` |
| Copy ideation: headline | `--headline` | `--headline "Ship Faster"` |
| Copy ideation: subhead | `--subhead` | `--subhead "Deploy in seconds"` |
| Copy ideation: CTA | `--cta` | `--cta "Get Started"` |
| Concept diversity: concept | Woven into `--prompt-seed` | Part of the seed text |
| Base image (interface mats) | `--base-image` | `--base-image /path/to/screenshot.png` |

---

## Required Planning Memo

Before validation, you should be able to state:

- chosen material type
- chosen route
- prior versions referenced
- required style reference versions
- blackboard learnings applied
- inspiration / references selected and what each contributes
- preserve / push / ban logic
- what is new in this run

If this memo is vague, the plan is not ready.

## Plan-Draft Flags Reference

Full flag set for `bgen plan-draft`:

| Flag | Description | Values |
|------|-------------|--------|
| `--material-type` | Required. Type of material | Any registered type |
| `--mode` | Generation mode | `reference`, `inspiration`, `hybrid` |
| `--mechanic` | Visual mechanic | Free text |
| `--purpose` | What job the material does | Free text |
| `--target-surface` | Where it appears | Free text |
| `--product-truth-expression` | Product truth to express | Free text |
| `--abstraction-level` | How abstract the concept | `low`, `medium`, `high` |
| `--render-backend` | Rendering approach | `native`, `html` |
| `--design-variance` | Creativity dial (1-10) | Integer |
| `--preserve` | Keep this element (repeatable) | Free text |
| `--push` | Amplify this element (repeatable) | Free text |
| `--ban` | Prohibit this element (repeatable) | Free text |
| `--pick` | Select a role (repeatable) | `role=source` |
| `--prompt-seed` | Creative direction seed | Free text |
| `--base-image` | Product screenshot for interface materials | File path |
| `--source-url` | Source URL for proof-style materials | URL |
| `--entity-type` | Entity type for proof materials | Free text |
| `--output` | Output file path | File path |
| `--format` | Output format | `text`, `json` |

---

## Plan Review

**Why:** A weak plan produces weak output. Reviewing before validation catches
creative-direction problems that the automated validators cannot see.

Read the returned plan JSON. Check:

1. **Is the creative direction specific?** "A modern brand scene" is generic. "Terracotta
   column mark emerging from layered earth strata, warm directional light, single focal
   point with architectural negative space" is specific.

2. **Are inspiration sources appropriate?** A concept illustration should not reference
   social post layouts. A social post should not reference large-format poster composition.

3. **Are there warnings?** The plan-draft command emits warnings about weak setup,
   missing references, or mode concerns. Read them.

4. **Does the prompt seed reflect the philosophy?** If the philosophy emphasizes natural
   materials and the prompt says "sleek glass interface", there is a disconnect.

5. **Does the plan visibly use blackboard and prior winners?** If the plan could have
   been written without reading them, it is too generic.

6. **Will the planned evidence actually survive into generation?** If the selected model/wrapper
   only uses refs for prompt routing/context, do not overstate how much grounding you have.

7. **Is the style anchor truly locked?** If learnings say a prior version is required to hold
   the art direction, the plan should make that mandatory. “We looked at v014” is not enough.

If the plan is generic or has warnings about creative direction, refine the prompt seed
and rerun plan-draft once. Do not rerun more than once at this stage — Phase 3 provides
the formal quality gate.

---

## Interface Material Planning

**Why:** Interface materials (browser-illustration, landing-hero, product-banner,
feature-illustration) need special handling because they depict the actual product.
Without a real screenshot, image models invent fake UI.

For these material types, ALWAYS:

1. Pass `--base-image <screenshot-path>` to `bgen plan-draft`
2. Select the screenshot from `.brand-gen/brands/<active>/product-shots/` that best
   matches the material purpose
3. If no screenshots exist, capture them first:
   ```bash
   source .venv/bin/activate && bgen capture-product \
     --url <app-url> \
     --out-dir .brand-gen/brands/<active>/product-shots
   ```

Never proceed to Phase 3 without a base image for interface materials.

But if the user explicitly asked for illustration-only artwork, do not solve that request by picking an interface material purely because base-image support exists. Re-route to a standalone illustration material, or use `feature-illustration` only with explicit standalone-art constraints, and keep the screenshot as a semantic truth reference instead.
