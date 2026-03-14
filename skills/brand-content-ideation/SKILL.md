---
name: brand-content-ideation
description: >
  Ideate branded content — what to say, who to say it to, and which visual format fits.
  Produces structured content briefs that feed directly into brand-gen pipeline as prompt seeds.
  USE WHEN user wants to create branded social content, carousel slides, editorial cards,
  educational materials, or needs help figuring out what messaging to put on brand materials.
  USE WHEN user says "what should I post", "help me ideate content", "create a carousel",
  "make content cards", or "figure out what to say".
  DON'T USE WHEN: user already has exact copy and just needs generation (use brand-gen directly).
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Content Ideation

Turn brand truth into publishable content. This skill bridges the gap between
"we have a brand identity" and "we have content worth posting."

## The problem this solves

brand-gen generates visuals. But before you can generate a content card or carousel,
you need to decide: **what is the card about?** What headline, what body text, what CTA?
Most brand tools skip this step and leave you staring at a blank prompt.

## Ideation → Generation Pipeline

```
1. Gather brand context       (auto — from brand identity)
2. Ask discovery questions     (interactive — 3-5 questions)
3. Generate content brief      (structured — topic + angle + copy + format)
4. Map brief to material type  (auto — content-card, editorial-card, carousel-slide)
5. Feed to brand-gen pipeline  (auto — prompt_seed + material_type + copy)
```

## Step 1: Gather brand context

Before asking the user anything, load the brand's stored context:

```bash
python3 mcp/brand_iterate.py show-session-summary --format json
```

Extract from the identity:
- **Brand pillars**: identity_core.tone_words → what themes the brand owns
- **Messaging**: messaging.tagline, messaging.elevator, messaging.value_propositions
- **Voice**: messaging.voice.description, messaging.voice.tone_words
- **Approved copy**: messaging.approved_copy_bank (headlines, subheadlines, slogans)
- **Product truth**: brand.summary — what the product actually does

## Step 2: Discovery questions

Ask **3-5 questions** to narrow the content brief. Never ask all at once — ask one, respond, ask next.

### Question bank (pick the most relevant 3-5)

**Purpose questions:**
- What is the one thing you want the audience to understand or do after seeing this?
- Is this awareness (teaching), consideration (comparing), or decision (proving)?
- Are you educating existing users or attracting new ones?

**Audience questions:**
- Who specifically sees this? (developers, executives, general public, existing customers)
- What does this audience already know about your product/space?
- What is their biggest misconception or pain point?

**Content questions:**
- Do you have a specific topic, stat, or announcement to share?
- Is this part of a series or a standalone piece?
- What is the "radical truth" or surprising take you can offer?

**Format questions:**
- Is this a single card, a multi-slide carousel, or an article header?
- Which platform is primary? (LinkedIn, Instagram, X, blog, newsletter)
- Do you want a photo inset, pure typography, or illustration + text?

**Tone questions:**
- Should this feel educational, provocative, celebratory, or urgent?
- Are you speaking as a brand or as a person behind the brand?

### Platform → format routing

| Platform | Best format | Material type |
|----------|------------|---------------|
| LinkedIn (single) | Editorial card with CTA | `editorial-card` |
| LinkedIn (carousel) | 4-8 slide series | `carousel-slide` |
| Instagram (carousel) | 4-10 portrait slides | `carousel-slide` |
| Instagram (single) | Content card with photo | `content-card` |
| X/Twitter | Square or landscape card | `content-card-square` or `x-card` |
| Blog header | Editorial card with headline | `editorial-card` |
| Newsletter | Content card or info-card | `info-card` |

## Step 3: Generate content brief

After discovery, produce a structured brief:

```json
{
  "content_type": "carousel",
  "platform": "linkedin",
  "material_type": "carousel-slide",
  "topic": "Why governance matters for AI agents",
  "angle": "Most AI agents have no accountability. Here's why that's about to change.",
  "audience": "Technical founders and AI engineers",
  "funnel_stage": "awareness",
  "slide_count": 6,
  "slides": [
    {
      "slide": 1,
      "role": "hook",
      "headline": "Your AI agent has more power than most employees.",
      "subhead": "But zero accountability.",
      "body": "",
      "visual": "typography-only, bold display font on brand background"
    },
    {
      "slide": 2,
      "role": "empathy",
      "headline": "",
      "subhead": "The problem",
      "body": "AI agents can deploy code, move money, and make decisions. But there's no governance layer. No audit trail. No community oversight.",
      "visual": "text on branded field"
    },
    {
      "slide": 3,
      "role": "value",
      "headline": "On-chain governance for AI",
      "subhead": "",
      "body": "Sage Protocol gives every agent a governance stack: proposals, voting, reputation, and transparent decision logs.",
      "visual": "text + subtle brand illustration"
    },
    {
      "slide": 4,
      "role": "value",
      "headline": "How it works",
      "subhead": "",
      "body": "1. Agents register with a DAO\n2. Actions require governance approval\n3. Community votes on agent behavior\n4. Reputation accrues over time",
      "visual": "numbered list on branded field"
    },
    {
      "slide": 5,
      "role": "proof",
      "headline": "Already live",
      "subhead": "",
      "body": "3 active DAOs, 12 governed agents, 200+ proposals executed on Base.",
      "visual": "stat highlight on brand accent"
    },
    {
      "slide": 6,
      "role": "cta",
      "headline": "Start governing your agents →",
      "subhead": "sageprotocol.io",
      "body": "",
      "visual": "CTA card with brand mark"
    }
  ],
  "voice_notes": "Direct, confident, no hype. Speak to builders who want reliable tooling."
}
```

## Step 4: Map brief to brand-gen pipeline calls

Each slide or card becomes a brand-gen pipeline call:

```bash
# Single content card
python3 mcp/brand_iterate.py pipeline \
  --material-type content-card \
  --prompt-seed "Headline: Your AI agent has more power than most employees. Subhead: But zero accountability. Body: [none]. Visual: typography-only, bold display font on copper brand background, brand mark bottom-left." \
  --mode hybrid \
  --format json

# Or via MCP
brand_pipeline(
  material_type="content-card",
  prompt_seed="Headline: Your AI agent has more power than most employees. Subhead: But zero accountability. Visual: bold typography-only card on warm cream field with brand mark bottom-left.",
  mode="hybrid"
)
```

### Carousel generation pattern

For multi-slide carousels, generate each slide separately with slide numbering:

```bash
for slide in 1 2 3 4 5 6; do
  python3 mcp/brand_iterate.py pipeline \
    --material-type carousel-slide \
    --prompt-seed "[slide $slide copy from brief]" \
    --mode hybrid \
    --format json
done
```

## Step 5: Review and iterate

After generation, review the output:
1. Does the text hierarchy read clearly at mobile size?
2. Is the brand mark visible but not dominant?
3. Does the content card feel editorial, not template-y?
4. For carousels: do the slides feel like a cohesive series?

Use `brand_pipeline` with `--base-image` to refine existing cards (add photo insets, adjust text placement).

## Content architecture patterns

### The Tia Health pattern (from your examples)

These screenshots show three distinct card archetypes:

1. **Step card**: "Step One: Establishment of Care" — step number + italic title + colored subhead + body text + photo circle inset + brand mark
2. **Article card**: "Cholesterol and Dementia" — large serif headline (mixed italic) + body paragraph + "Read more →" CTA + brand mark
3. **Social post card**: Illustration + large bold statement + brand colors as atmosphere
4. **Info card**: Subhead + body text + bullet list with colored bullets + photo circle inset + brand mark

### Prompt seed patterns for each archetype

**Step card:**
```
Step [N]: [Title in italic display font]. Subhead: [Topic] in colored accent. Body: [2-3 sentences explaining the step]. Bottom-right: circular photo inset of [scene]. Bottom-left: brand mark. Background: [brand background color] solid field.
```

**Article card:**
```
Large headline in display font: [Title]. Partial italic emphasis on [key phrase]. Body paragraph: [3-4 sentences]. CTA: "Read more on this →" right-aligned. Brand mark bottom-left. Background: [brand accent color] solid field. No images — pure typography card.
```

**Info card:**
```
Subhead: [Topic] in bold accent color. Body: [1-2 sentences]. Bullet list with colored bullets: [item 1], [item 2], [item 3], [item 4], [item 5]. Bottom-right: circular photo inset. Brand mark bottom-left. Background: [brand light color].
```

## What NOT to do

- Don't generate content cards with empty/vague text — the copy must be real and intentional
- Don't use brand-gen for text layout when you could use a design tool — brand-gen generates imagery, not pixel-perfect typography
- Don't ask the image model to render long body paragraphs — keep body text to 2-3 sentences max
- Don't generate carousels with inconsistent brand treatment across slides
- Don't skip the discovery questions — the whole point is figuring out *what to say*

## Reference material

For detailed platform specs, aspect ratios, and safe zones:
- `references/content-card-specs.md` — platform-specific dimensions and typography rules
