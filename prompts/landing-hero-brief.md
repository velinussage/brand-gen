# Landing Hero Brief

Use this when the user wants a **real homepage hero**, not just a product banner.

## A landing hero must include

- brand logo / wordmark
- top navigation
- headline
- subheadline
- CTA button(s)
- branded background treatment
- one real product visual

If those are not explicit in the brief, the output will drift into a generic product image.

## Core rule

For landing heroes, separate the work into two layers:

1. **deterministic structure**
   - logo
   - nav
   - headline
   - CTA
   - trust row
   - product screenshot placement

2. **optional generative treatment**
   - background atmosphere
   - screenshot framing ideas
   - editorial polish

Do not rely on image generation alone for exact hero text or nav structure.
Do not rely on fixed pixel guesses for header spacing either. Deterministic heroes should measure nav labels, CTA widths, and proof-row items so spacing stays balanced when copy changes.
When a `brand-profile.json` or `brand-identity.json` is present, the composer should also inherit palette, typography, radius, and spacing cues from stored design tokens before falling back to generic defaults.

## Required inputs

- brand name
- logo path
- headline
- subheadline
- nav items
- header CTA
- primary CTA
- secondary CTA
- one or two real product screenshots
- target palette
- layout mode

## Copy structure

For hero copy, use this spine:

1. **Hook** — short eyebrow or opening frame
2. **Promise** — the headline
3. **Proof** — the subheadline and trust row
4. **Action** — CTA(s)

If the subheadline just repeats the headline, rewrite it.
If the trust row just repeats category words, replace it with proof.

## Good hero-reference pattern

Use official product homepages first:
- Notion
- Cursor
- Linear
- Coda / Superhuman
- Granola

Use agency portfolios second:
- Clay
- Ramotion
- Focus Lab

Official product pages are better for:
- text-to-product balance
- nav treatment
- safe headline area
- CTA hierarchy

Agency portfolios are better for:
- spacing taste
- framing
- background polish

## Review rule

After composing a hero, always run a critique/refine pass:

```bash
python3 mcp/brand_iterate.py review-brand <version>
```

Review for:
- strategic/message clarity
- copy strength
- composition/balance
- product fidelity

## Recommended command

```bash
python3 mcp/brand_iterate.py pipeline \
  --material-type landing-hero \
  --goal "Homepage hero with logo, nav, headline, subheadline, CTAs, and real product shots" \
  --request "Generate a landing hero for Acme"
```
