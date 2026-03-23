# Design Philosophy Framework

A design philosophy is a named aesthetic movement — a poetic, opinionated worldview that guides every visual decision. It sits above mechanical design rules (hex codes, font names, shape tokens) and below individual material briefs, providing the creative DNA that makes a brand's outputs feel authored rather than assembled.

Every brand in brand-gen should have a design philosophy before generating materials.

## Why This Matters

Without a philosophy, the pipeline produces technically correct but soulless output. Materials hit the right colors and fonts but feel interchangeable — any brand could have made them. The philosophy provides:

- **A named identity** for the aesthetic direction (2 words max)
- **Creative constraints** that are evocative, not mechanical
- **A craftsmanship standard** that prevents AI-generated feel
- **Interpretive room** for each material type to express the philosophy differently

## How to Create a Design Philosophy

### Step 1: Name the Movement (1-2 words)

The name captures the aesthetic tension or central metaphor. It should feel like an art movement, not a marketing tagline.

**Strong names:**
- "Structural Reverence" — monumental architecture meets digital ephemerality
- "Chromatic Silence" — color as the primary information system, everything else quiet
- "Metabolist Dreams" — organic growth patterns through systematic geometry
- "Analog Meditation" — texture and breathing room as primary materials
- "Concrete Poetry" — massive form and bold geometry as communication

**Weak names:**
- "Modern Professional" — describes nothing specific
- "Clean and Bold" — two generic adjectives
- "Tech Forward" — meaningless industry jargon

### Step 2: Articulate the Philosophy (4-6 paragraphs)

Each paragraph should cover a distinct design dimension. Never repeat the same point about color or spacing. Cover:

1. **Space and form** — How does the philosophy treat empty space? Is it earned or given? What forms dominate — geometric, organic, architectural, typographic?

2. **Color and material** — What is the color logic? Not hex codes, but the *feeling* of the palette. What real-world materials does it evoke? Fired earth, linen, concrete, aged paper?

3. **Scale and rhythm** — Does the system operate at one scale or two? How do elements repeat? Architectural regularity or organic clustering? What creates visual tempo?

4. **Composition and balance** — How many dominant gestures per piece? What's the relationship between primary and secondary elements? Symmetry, asymmetry, or deliberate tension?

5. **Visual hierarchy** — How does information organize itself? Through weight? Through position? Through absence? What does the eye find first, second, third?

### Step 3: Embed the Craftsmanship Standard

The philosophy MUST emphasize that final work should appear:
- Meticulously crafted, not generated
- The product of deep expertise and painstaking attention
- Master-level execution where every alignment is deliberate
- Indistinguishable from work by a human designer at the top of their field

Repeat this framing in different ways throughout the philosophy. This is the antidote to AI slop.

### Step 4: Leave Creative Space

The philosophy guides interpretation — it does not prescribe layouts. It should be specific enough to exclude generic work but open enough that a campaign poster, a social card, and a brand scene all feel like expressions of the same movement.

## Philosophy Structure Template

```
# [Movement Name]

[Opening paragraph — the central metaphor and what makes this aesthetic movement
distinctive. What world does this work inhabit? What tension does it hold?]

[Space and form — how emptiness and structure relate. What architectural or
natural logic governs placement? How is negative space treated?]

[Color and material — the palette as felt experience, not as hex values.
What real-world surfaces and substances does the work evoke?]

[Scale and rhythm — the visual tempo. How elements repeat, vary, and create
movement across the composition. What registers does the work operate at?]

[Composition and hierarchy — the rule of dominance. How many moves per piece?
What does restraint look like in this movement? How does the eye travel?]

[Craftsmanship close — the quality standard. What separates this work from
everything else? What does mastery look like in this aesthetic?]
```

## Examples

### "Concrete Poetry"

Communication through monumental form and bold geometry. Visual expression: massive color blocks, sculptural typography (huge single words, tiny labels), Brutalist spatial divisions, Polish poster energy meets Le Corbusier. Ideas expressed through visual weight and spatial tension, not explanation. Text as rare, powerful gesture — never paragraphs, only essential words integrated into the visual architecture. Every element placed with the precision of a master craftsman who has spent decades understanding the weight of a single letterform.

### "Chromatic Language"

Color as the primary information system. Geometric precision where color zones create meaning. Typography minimal — small sans-serif labels letting chromatic fields communicate. Think Josef Albers' interaction meets data visualization. Information encoded spatially and chromatically. Words only to anchor what color already shows. The result of painstaking chromatic calibration, where every hue relationship has been tested, adjusted, and refined until the palette feels inevitable rather than chosen.

### "Analog Meditation"

Quiet visual contemplation through texture and breathing room. Paper grain, ink bleeds, vast negative space. Photography and illustration dominate. Typography whispered — small, restrained, serving the visual. Japanese photobook aesthetic. Images breathe across compositions. Text appears sparingly, positioned with the same care a calligrapher gives to a single brushstroke. Each piece balanced as if someone spent hours adjusting a single element by millimeters.

## Using the Philosophy in Brand-Gen

Once created, the design philosophy is stored at:

```text
.brand-gen/brands/<brand>/design-philosophy.md
```

The runtime should reference it anywhere the system is deciding how the brand ought to feel:

1. **Plan** — `plan-material` / `plan-draft` should use it to shape the prompt seed, preserve/push/ban lists, abstraction level, and composition mechanic.
2. **Review** — `critique-plan`, `review-prompt`, and `review-brand` should use it as a quality bar, not just a mood reference.
3. **Learning loop** — `submit-critique`, `feedback`, and iteration notes should refine how the philosophy is interpreted over time.

### Philosophy → Prompt Translation

The philosophy informs prompt seeds but is NOT pasted verbatim into image prompts. Instead:

- Extract the **material metaphors** ("fired earth", "aged stone", "linen texture")
- Extract the **compositional rules** ("one dominant gesture", "architectural rhythm")
- Extract the **quality boosters** ("meticulous", "labored over", "masterful")
- Weave these into the prompt seed naturally

### Philosophy → Critique Calibration

When scoring outputs, add a philosophy axis:

- **Philosophy fit** (1-5): Does this feel like a work from the named movement? Would someone familiar with the philosophy recognize it? Or could any brand have produced this?

## Avoiding Common Mistakes

- **Too mechanical**: "Use 16px spacing with 4px border radius" — this is a spec, not a philosophy
- **Too vague**: "Make it beautiful and modern" — this guides nothing
- **Too trendy**: "Glassmorphism with neon accents" — dated within months
- **Too derivative**: "Make it look like Apple" — copying, not creating
- **Too long**: Philosophies over 6 paragraphs lose focus and become prescriptive

## The Craftsmanship Imperative

The philosophy exists to make work that could not have been generated by a default AI pipeline. Every material should appear as though someone at the absolute top of their field labored over every detail with painstaking care — the composition, the spacing, the color relationships, the typographic weight. The philosophy provides the creative vision. The craftsmanship standard ensures it's executed at a level that commands respect.

The test: if someone said "AI made this," they should be wrong — and visibly so.

## Cultivation, Not One-Shot Creation

A design philosophy is a living document. It is refined through three feedback loops:

### 1. Source Vault Reading

Most brands have existing thinking scattered across documents — brand sessions, positioning decks, messaging playbooks, design language docs. The philosophy should be **distilled from these sources**, not generated from nothing.

Before creating a philosophy, read the brand's source vault deeply. The metaphors, emotional territory, and design principles are already there. Your job is to find the through-line and name it.

### 2. User Dialogue

Every philosophy creation or refinement should include at least one targeted question to the brand owner. Not "what do you want?" but specific questions that reference vault content:
- "The vault describes both institutional gravitas and organic warmth. Which feels more central to the visual future?"
- "Your aspirational brands span Stripe (precision) and Aesop (restraint). Where does the philosophy sit on that spectrum?"

### 3. Generation Feedback Loop

After 5+ scored generations, check:
- Do high-scoring outputs share aesthetic qualities not yet captured in the philosophy?
- Do low-scoring outputs fail in ways the philosophy should explicitly address?
- Has the user expressed preferences that suggest the philosophy needs adjustment?

### Refinement Triggers

Re-evaluate the philosophy when:
- The brand vault has been updated since the philosophy was written
- 5+ new generations have been scored
- `philosophy_fit` scores consistently fall below 3
- The user explicitly requests a direction change
- New inspiration sources are added to the workspace

### Propose, Don't Overwrite

When refining, always present proposed changes to the brand owner before updating. The philosophy belongs to the human, not the agent. Show what you'd change and why, citing the source (vault content, score data, user feedback) that motivates each change.
