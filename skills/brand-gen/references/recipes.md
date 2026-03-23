# Complex Workflow Recipes

Multi-step workflows that need more guidance than the main skill provides.

## Table of Contents

- [Live app capture → social card](#live-app-capture--social-card)
- [Base-image editing / overlays](#base-image-editing--overlays)
- [Carousel generation](#carousel-generation)
- [Card composition rules](#card-composition-rules)
- [When to capture vs. use inspiration](#when-to-capture-vs-use-inspiration)

---

## Live app capture → social card

When a user wants a social card that shares **real product data** (a prompt, skill, feature page), use a **hybrid truth-first workflow**. Default to **raw screenshot + base-image editing** first. Deterministic composition is a fallback for extreme text-integrity cases, not the default.

### Decision: capture vs. inspiration

Use **live app captures** when:
- the card should show real names, statuses, copy, metadata, or UI structure
- the user wants to share a specific prompt, skill, library, or page from the product
- the asset should read as **proof** ("this exists now"), not concept art
- previous generations garbled or abstracted the text

Use **inspiration refs** when:
- the material needs better taste, pacing, or composition
- the product truth is already covered by a screenshot but the framing feels flat
- you need help with hierarchy, crop discipline, whitespace, or surface attitude

### Recipe

1. **Capture the live detail page**

```bash
python3 scripts/product_screens.py capture \
  --session live-share-capture \
  --shot skill-detail=https://app.example.com/skills/skill-detail \
  --out-dir /abs/path/to/brand-materials/product-screens-live
```

Capture the **specific detail page**, not a generic overview. A prompt/skill detail page is better than a feed screenshot.

2. **Default path: edit the raw screenshot into a branded state card**

```bash
bgen pipeline \
  --material-type state-card \
  --base-image /abs/path/to/product-screens-live/skill-detail-01.png \
  --pick product_truth=/abs/path/to/product-screens-live/skill-detail-01.png \
  --pick motif=/abs/path/to/brand/logo.png \
  --prompt-seed "Turn this real product screenshot into a premium square state-share card. Preserve the visible page title, UI labels, and product structure. Reframe it into one bounded carrier with a subtle illustrated background field and stronger editorial crop. No invented text and no decorative overlays on top of the UI." \
  --format json
```

Prefer this for prompt/skill detail pages. It keeps the output more aesthetic than a deterministic card while still anchoring on real product truth.

3. **Fallback only when exact text integrity keeps drifting: use the official HTML share-card path**

```bash
bgen pipeline \
  --material-type announcement-card \
  --render-backend html \
  --source-url "https://app.example.com/skills/skill-detail" \
  --entity-type skill \
  --proof-meta "Live product detail" \
  --proof-row "Structured, source-derived share card" \
  --format json
```

This is the public deterministic route. It derives structured share-card content from the source URL and renders it through the HTML card engine instead of relying on a private host script.

4. **Optional advanced local path: compose a screenshot-backed carrier yourself**

If you already have the screenshot and want a manual carrier image before any polish step, the repo still ships a utility script:

```bash
python3 scripts/compose_live_share_card.py \
  --screenshot /abs/path/to/product-screens-live/skill-detail-01.png \
  --title "browser-automation-skill" \
  --subtitle "Headless browser automation for agents" \
  --community "Example Community" \
  --eyebrow "New skill" \
  --badge "Skill" \
  --screenshot-label "Live app detail" \
  --logo /abs/path/to/brand/logo.png \
  --output /abs/path/to/live-social-cards/skill-share-base.png
```

Use this only when you explicitly need a screenshot-backed base image that you control by hand.

5. **Optional: polish the deterministic carrier with Flux (don't redraw the truth)**

```bash
bgen pipeline \
  --material-type social \
  --base-image /abs/path/to/live-social-cards/skill-share-base.png \
  --image /abs/path/to/brand/logo.png \
  --prompt-seed "Polish this existing square social card carrier only. Keep the screenshot inset, title, subtitle, metadata pill, and card geometry intact. Do not redraw the product UI. Do not rewrite any visible text. Keep every element fully inside the rounded card. Improve the brand carrier with a quieter premium background field, subtle texture, cleaner spacing, and more editorial finish." \
  --format json
```

Use this only if the raw-screenshot state-card path still fails and the user prefers truth over taste.

6. **If needed, normalize to platform size**

Some edit models return a model-native size (e.g., `1008x1008`) even when the base was `1200x1200`. Resize after the edit pass:

```python
from PIL import Image
Image.open("polished.png").resize((1200, 1200), Image.Resampling.LANCZOS).save("final.png")
```

### Composition pattern

The strongest pattern for live data cards:
- one branded outer card
- one real product truth surface
- one bounded carrier around that surface
- optional short deterministic title/subtitle only when the screenshot alone is not enough
- one or two quiet metadata pills
- no extra floating UI fragments outside the card

Ban elements that bleed past the card edge, float outside the frame, or cross the border. Prefer one inset maximum and one clear title block.

---

## Base-image editing / overlays

When the user has an existing image and wants branded overlays, text, icons, or edits on top of it.

```bash
bgen pipeline \
  --material-type podcast-cover \
  --base-image /path/to/photo.jpg \
  --image /path/to/brand-mark.png \
  --prompt-seed "Add title bar with 'Intro to X' and pillar mark icon in bottom-left" \
  --format json
```

**What happens**: auto-selects `flux-2-pro`. The base image is the primary input; brand reference assets are additional references. The prompt instructs the model what to add/overlay.

**Prompt style**: use instruction language ("Add X to Y", "Place Z in bottom-left"), not descriptive language ("A poster with X and Y"). The model edits the existing image rather than generating from scratch.

**Extra references**: pass stored brand assets via `--image` alongside `--base-image` — e.g., the pillar mark PNG so the model knows exactly what icon to place.

---

## Carousel generation

For multi-slide carousels, generate each slide separately with the content brief:

```bash
# Plan the content brief first (or use brand-content-ideation skill)
bgen ideate-copy --material-type carousel-slide --goal "..." --format json

# Generate each slide
bgen pipeline --material-type carousel-slide \
  --prompt-seed "Slide 1/6 — Hook. Headline: 'Your AI agent has more power than most employees.' Subhead: 'But zero accountability.' Visual: typography-only, bold display font on brand background." \
  --mode hybrid --format json
```

### Carousel narrative arc

| Slide | Role | Design treatment |
|-------|------|-----------------|
| 1 | Hook | One oversized headline, minimal text, high contrast |
| 2 | Empathy | Validate the pain point, 2-3 sentences |
| 3-6 | Value | Key info, one point per slide |
| 7 | Proof | Stats, testimonials, or case study |
| 8 | CTA | Clear call-to-action + brand mark |

### Platform dimensions

| Platform | Ratio | Resolution | Max slides |
|----------|-------|-----------|------------|
| Instagram | 4:5 | 1080x1350 | 20 |
| LinkedIn | 4:5 or 1:1 | 1080x1350 or 1080x1080 | 10-12 |
| X/Twitter | 16:9 or 1:1 | 1600x900 or 1080x1080 | 4 |

Run `bgen social-specs` for live platform dimensions.

---

## Card composition rules

### Explicit card bounds

For card-style generations, protect the card bounds in the prompt:
- the screenshot/inset must sit **fully inside one rounded card**
- ban elements that bleed past the card edge, float outside the frame, or cross the border
- prefer one inset maximum and one clear title block
- if repeated generations leak content outside the card, switch to base-image editing or deterministic composition

### Typography hierarchy for content cards

- **Headline**: 36pt+ display font, can be 48-72pt for hook slides
- **Subhead**: 24-28pt, accent color or bold weight
- **Body text**: 22-24pt minimum, regular weight
- **CTA text**: 20-24pt, with arrow marker

### Card archetypes

1. **Typography-only**: Headline dominates, body below, brand mark anchored
2. **Text + photo inset**: Text fills 70%, rounded photo circle in corner
3. **Text + illustration**: Branded illustration top, text block below
4. **List card**: Subhead + bullet list, clean whitespace
5. **Stat highlight**: One big number + context sentence

---

## When to capture vs. use inspiration

| Signal | Use live app capture | Use inspiration refs |
|--------|---------------------|---------------------|
| Card should show real product data | Yes | No |
| Previous generations garbled text | Yes | No |
| Asset should read as "proof" | Yes | No |
| Need better taste/composition | No | Yes |
| Product truth already covered by screenshot | No | Yes |
| Need help with hierarchy or whitespace | No | Yes |

Best default for product-sharing social cards:
1. Capture **one targeted live product screenshot** (prefer detail pages over generic feeds)
2. Pass as `--pick product_truth=/abs/path/to/capture.png`
3. Add **one** application/composition inspiration ref for polish
4. Keep copy deterministic and short

If the user needs exact live app data preserved and image generations keep abstracting it, prefer a deterministic composed card over another freeform image-model pass.
