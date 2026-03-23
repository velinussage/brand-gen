---
name: brand-content-ideation
description: >
  Ideate branded content — figure out what to say, who to say it to, and which visual format
  fits. Produces structured content briefs that feed directly into brand-gen pipeline as prompt
  seeds. Use when the user wants to create branded social content, carousel slides, editorial
  cards, educational materials, or needs help figuring out what messaging to put on brand
  materials. Triggers on: "what should I post", "help me ideate content", "create a carousel",
  "make content cards", "figure out what to say", "content strategy", "social content plan",
  "editorial cards", "content brief", "what should the card say". Don't use when the user
  already has exact copy and just needs generation — use brand-gen directly.
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Content Ideation

Turn brand truth into publishable content. This skill bridges the gap between "we have a brand identity" and "we have content worth posting."

## The problem this solves

brand-gen generates visuals. But before generating a content card or carousel, you need to decide: **what is the card about?** What headline, what body text, what CTA? This skill answers that question.

## Pipeline

```
1. Gather brand context       (auto — from brand identity)
2. Ask discovery questions     (interactive — 3-5 questions)
3. Generate content brief      (structured — topic + angle + copy + format)
4. Map brief to material type  (auto — content-card, editorial-card, carousel-slide)
5. Feed to brand-gen pipeline  (auto — prompt_seed + material_type + copy)
```

## Step 1: Gather brand context

Before asking the user anything, load stored context:

```bash
bgen show-session-summary --format json
```

Extract:
- **Brand pillars**: `identity_core.tone_words`
- **Messaging**: `messaging.tagline`, `messaging.elevator`, `messaging.value_propositions`
- **Voice**: `messaging.voice.description`, `messaging.voice.tone_words`
- **Approved copy**: `messaging.approved_copy_bank` (headlines, subheadlines, slogans)
- **Product truth**: `brand.summary`

## Step 2: Discovery questions

Ask **3-5 questions** to narrow the content brief. Ask one at a time, respond, then ask next.

### Question bank (pick the most relevant 3-5)

**Purpose**: What should the audience understand or do after seeing this? Is this awareness, consideration, or decision? Educating existing users or attracting new ones?

**Audience**: Who sees this? What do they already know? What's their biggest misconception or pain point?

**Content**: Do you have a specific topic, stat, or announcement? Part of a series or standalone? What's the surprising take you can offer?

**Format**: Single card, carousel, or article header? Primary platform? Photo inset, pure typography, or illustration + text?

**Tone**: Educational, provocative, celebratory, or urgent? Speaking as a brand or as a person behind the brand?

### Platform → format routing

| Platform | Best format | Material type |
|----------|------------|---------------|
| LinkedIn (single) | Editorial card with CTA | `editorial-card` |
| LinkedIn (carousel) | 4-8 slide series | `carousel-slide` |
| Instagram (carousel) | 4-10 portrait slides | `carousel-slide` |
| Instagram (single) | Content card with photo | `content-card` |
| X/Twitter | Square or landscape card | `content-card-square` or `x-card` |
| Blog header | Editorial headline card | `editorial-card` |
| Newsletter | Content or info card | `info-card` |

## Step 3: Generate content brief

After discovery, produce a structured brief:

```json
{
  "content_type": "carousel",
  "platform": "linkedin",
  "material_type": "carousel-slide",
  "topic": "Why [key concept] matters for [audience]",
  "angle": "Most [audience pain point]. Here's why that's about to change.",
  "audience": "Technical founders and engineers",
  "funnel_stage": "awareness",
  "slide_count": 6,
  "slides": [
    {
      "slide": 1,
      "role": "hook",
      "headline": "[Bold attention-grabbing statement]",
      "subhead": "[Consequence or contrast]",
      "body": "",
      "visual": "typography-only, bold display font on brand background"
    },
    {
      "slide": 2,
      "role": "empathy",
      "headline": "",
      "subhead": "The problem",
      "body": "[Validate the pain point in 2-3 sentences]",
      "visual": "text on branded field"
    },
    {
      "slide": 3,
      "role": "value",
      "headline": "[Key value proposition]",
      "subhead": "",
      "body": "[How the product solves the problem]",
      "visual": "text + subtle brand illustration"
    },
    {
      "slide": 4,
      "role": "proof",
      "headline": "[Evidence or stats]",
      "subhead": "",
      "body": "[Concrete numbers or testimonials]",
      "visual": "stat highlight on brand accent"
    },
    {
      "slide": 5,
      "role": "cta",
      "headline": "[Clear call to action]",
      "subhead": "[URL or next step]",
      "body": "",
      "visual": "CTA card with brand mark"
    }
  ],
  "voice_notes": "Direct, confident, no hype. Speak to builders who want reliable tooling."
}
```

## Step 4: Map brief to brand-gen pipeline calls

Each slide or card becomes a pipeline call:

```bash
# Single content card
bgen pipeline \
  --material-type content-card \
  --prompt-seed "Headline: [headline]. Subhead: [subhead]. Visual: typography-only, bold display font on brand background, brand mark bottom-left." \
  --mode hybrid \
  --format json
```

### Carousel generation

Generate each slide separately with slide numbering:

```bash
bgen pipeline \
  --material-type carousel-slide \
  --prompt-seed "Slide 1/6 — Hook. Headline: '[headline]'. Visual: typography-only, bold display font on brand background." \
  --mode hybrid \
  --format json
```

See `references/content-card-specs.md` for platform dimensions, typography rules, and carousel narrative arc patterns.

## Step 5: Review and iterate

After generation, evaluate:
1. Does the text hierarchy read clearly at mobile size?
2. Is the brand mark visible but not dominant?
3. Does the content card feel editorial, not template-y?
4. For carousels: do the slides feel like a cohesive series?

Use `bgen pipeline --base-image ...` to refine existing cards (add photo insets, adjust text placement).

## Prompt seed patterns

**Typography-only card:**
```
Large headline in display font: [Title]. Subhead: [Subtitle] in accent color. Brand mark bottom-left. Background: [brand color] solid field. No images — pure typography card.
```

**Text + photo inset card:**
```
Subhead: [Topic] in bold accent. Body: [1-2 sentences]. Bullet list with colored bullets: [items]. Bottom-right: circular photo inset. Brand mark bottom-left. Background: [brand light color].
```

**Stat highlight card:**
```
One large number: [stat]. Context: [what it means in one sentence]. Brand accent background, brand mark bottom-left.
```

## What NOT to do

- Don't generate cards with empty/vague text — the copy must be real and intentional
- Don't ask the image model to render long body paragraphs — keep body to 2-3 sentences max
- Don't generate carousels with inconsistent brand treatment across slides
- Don't skip the discovery questions — the whole point is figuring out *what to say*
- Don't use brand-gen for pixel-perfect typography layout — it generates imagery, not typeset pages

## Reference files

- **`references/content-card-specs.md`** — platform dimensions, typography minimums, card archetypes, carousel narrative arc, and color treatment patterns
