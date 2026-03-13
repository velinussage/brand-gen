# UI / Product Visual Prompting Guide

Adapted from:
- UX Planet — *UI design with Midjourney*  
  https://uxplanet.org/ui-design-with-midjourney-df78eaa2d292

This guide adapts the article's useful UI-prompting ideas to **Replicate + brand-gen**.

## Official Midjourney lessons worth copying
From Midjourney's official docs, the useful transferable ideas are:
- short prompts often work better than long ones
- image prompts influence content and composition
- style references influence style, not subject truth
- moodboards can help unify taste across runs
- `--raw` is useful when you want less stylized, more literal adherence

For brand-gen, the direct translation is:
- keep prompt text concrete and short
- let reference images carry style and composition
- never ask one prompt to invent both the brand system and the presentation system

## What to borrow from the article

The article shows that UI prompts work better when you specify:
- the **surface type** (`landing page screenshot`, `dashboard`, `settings page`, `onboarding screen`)
- the **presentation context** (`browser window`, `MacBook`, `app screenshot`)
- the **visual style** (`minimalistic`, `flat design`, `clean UI`)
- the **frame/aspect** (often `16:9` for product and landing visuals)

## What to change for brand-gen

For brand-gen, do **not** use those words by themselves.

Always split the prompt into:
1. **product truth** — the real screenshot or UI crop that must stay accurate
2. **presentation treatment** — the browser frame, whitespace, background, crop, and polish

That means the article's UI keywords should guide **framing**, not trigger a UI redesign.

## Rapid iteration defaults for brand-gen

The purpose of brand-gen is to **rapidly try and iterate**, not to write one giant prompt and hope.

For screenshot-derived product marketing visuals, default to this stance:

- **Ramotion boldness**
  - one memorable move
  - stronger scale on the hero crop
  - fewer, larger surfaces instead of many small panels
- **MetaLab editorial framing**
  - calmer hierarchy
  - credible, spacious composition
  - more intentional negative space

Default composition discipline:
- one hero product window only
- one supporting inset maximum
- no synthetic app-shell expansion
- no extra nav, wallet bars, chat rails, or dashboard modules unless they exist in the approved screenshot crop
- when a result feels mid, remove elements before adding decoration
- do not reuse the same background field and floating-card composition across different material types

## Reference-crop protocol
Quality references matter more than more references.

For each material, prefer:
- one tightly cropped composition reference
- one tightly cropped motif/system reference
- one application reference showing how the system lands on a poster, badge sheet, motion frame, or product section

Avoid:
- full homepages when one case-study image is the real inspiration
- giant collage boards
- low-resolution screenshots with tiny details
- mixing too many unrelated agencies in one run

If a reference is supposed to teach:
- composition → crop to the whole layout
- motif → crop to the repeated graphic system
- application → crop to the poster, sticker sheet, merch, or hero block itself
- motion → crop a still from the strongest frame, or use a short motion reference outside the still generator

## Material-type differentiation

For rapid iteration, do not let every output become the same packaging move.

Different material types need different visual behavior:

- **browser-illustration**
  - clearer UI
  - quieter field
  - restrained framing
- **product-banner**
  - wider, more atmospheric
  - brand field does more work
  - often no inset
- **feature-illustration**
  - one product story
  - one graphic or explanatory device
  - tighter concept
- **styleframe**
  - motion-ready
  - bolder composition
  - more expressive brand field
- **social**
  - poster-like
  - phone-readable
  - fewer elements

Use:
- `prompts/material-type-differentiation.md`

## Core prompt recipe for screenshot-derived product visuals

```text
[real product screenshot as hero asset] +
[single hero product moment] +
[material role] +
[camera / crop distance] +
[brand field treatment] +
[graphic device] +
[surface type] +
[presentation stance] +
[presentation context] +
[composition / crop rule] +
[fidelity constraints]
```

Where `presentation stance` is explicit, for example:
- Ramotion boldness + MetaLab editorial framing
- Cursor product-truth restraint + Clay whitespace discipline
- Gretel pacing + BUCK system logic
- PORTO ROCHA contrast + MetaLab restraint

## Recommended UI vocabulary

### Surface type
- landing page screenshot
- dashboard screenshot
- settings page screenshot
- onboarding screen
- browser-based product interface
- admin panel
- feed view
- library view
- detail view

### Presentation context
- browser window
- desktop app frame
- MacBook-style product presentation
- launch visual
- product marketing image
- feed-safe social crop

### Style words
- minimalistic
- flat design
- clean UI
- airy spacing
- startup-like
- editorial polish
- subtle background
- soft depth

### Composition rules
- one clear product story
- tighter crop on the strongest component
- generous whitespace
- safe margins for social
- minimal or no text overlays
- one hero window
- one inset maximum
- subtract competing panels

## Fidelity constraints (always include for brand-gen)

- Do not redesign the UI
- Do not invent product copy
- Do not invent buttons, cards, labels, or metrics
- Preserve the actual navigation and interface hierarchy
- Preserve the real product structure
- Do not expand the app into a generic SaaS shell
- Do not synthesize a new header, chat sidebar, wallet strip, or bounty rail unless the approved screenshot already contains it
- Do not let the UI page title become the accidental campaign headline
- Do not reuse the same floating-card-on-cream composition when the material type changes

## Better prompt patterns

### Browser illustration / landing section
```text
Use the real product screenshot as the hero asset. This is a browser illustration, not a poster. Focus on one exact approved product moment. Ramotion boldness in crop and scale, MetaLab editorial framing in whitespace and restraint. Quiet brand field, restrained browser framing, readable UI, one secondary inset maximum. Do not redesign the UI. Do not invent labels, copy, panels, or a new app shell.
```

### X / feed visual
```text
Use the real product screenshot as the hero asset. This is a social poster, not a browser illustration. Product marketing image with a phone-readable focal crop, stronger contrast, one bold brand field, and zero or one supporting inset only if it improves the story. Ramotion boldness in the focal move, MetaLab restraint in clutter. Minimal or no text overlays. Do not redesign the UI. Do not invent cards, labels, panels, or product copy.
```

### More graphic / campaign-led variation
```text
Use the real product screenshot as the hero asset. Preserve the UI exactly. This is a styleframe or campaign still, not a screenshot board. One approved hero product moment only. Apply PORTO ROCHA-style graphic confidence to the brand field, Gretel-level discipline in pacing and type-safe spacing, and BUCK-style system clarity in how supporting shapes or motion cues are organized. Zero or one support crop only. No fake product chrome, no rewritten copy, and no campaign text inside the generated asset.
```

## Non-interface pattern for better prompts
When the material is not a UI visual, stop using abstract brand language as the main prompt.

Write prompts like:

```text
exact mark anatomy +
approved primitives +
exact number of outputs or modules +
layout structure +
finish +
negatives
```

Example:

```text
Use the exact logo anatomy: one broad horizontal cap and four vertical stems, cream on copper, with repeated square carriers and parallel line bands. Create one hero tile, one repeat tile, one border band, and one emblem variation only. Quiet cream editorial field, crisp line weights, no text, no extra symbols, no random rounded mosaics.
```

## Anti-patterns

- `"beautiful futuristic SaaS dashboard"` → too vague, too likely to redesign the product
- `"dribbble style dashboard"` → style-heavy, low fidelity to the real UI
- `"minimal clean landing page"` without mentioning the real screenshot → invites hallucinated layouts
- multiple conflicting styles (`minimalistic brutalist glassmorphism`) → weakens control
- asking the model to "make it feel more complete" → often causes fake nav, fake chat, fake cards, and generic SaaS chrome
- feeding multiple screenshots without naming the **single hero product moment** → often causes mushy multi-panel composites
- using the same warm-neutral field + floating white card + one inset across several material types → convergence, weak brand range
- letting `Network activity` or another UI heading become the hero copy by accident → screenshot packaging, not campaign composition

## Best use in brand-gen

- Use this guide when writing prompts for:
  - `browser-illustration`
  - `product-banner`
  - `x-feed`
  - `linkedin-card`
  - `linkedin-feed`
- Combine it with:
  - `prompts/product-presentation-reference-brief.md`
  - `prompts/social-image-brief.md`
