# Social Image Brief

Use this for X cards, X feed posts, LinkedIn cards, LinkedIn feed posts, OG cards, and other social visuals.

## Required inputs
- Brand description
- Product / feature name
- Target platform
- Product-truth screenshot
- Presentation reference(s)
- Headline / subheadline
- Desired tone

## Composition goals
- Keep the real product UI as the hero asset
- Do not redesign the UI
- Do not invent buttons, cards, labels, or fake product copy
- Keep headline-safe negative space
- Make the product/browser visual instantly readable
- Preserve brand style without feeling template-driven
- Prefer one hero product crop and zero supporting insets unless the second surface adds proof
- If the model starts inventing product chrome, reduce the number of reference surfaces and tighten the crop
- Tailor the tone per platform:
  - X: bolder, faster, higher contrast
  - X feed: stronger focal crop, clearer mobile readability
  - LinkedIn: cleaner, more editorial, more professional
  - LinkedIn feed: slightly calmer hierarchy and more whitespace than X
  - OG: universal, legible, link-preview friendly
- Do not let social visuals become mini landing pages or tiny screenshot boards

## Stance defaults

- **X / X feed**
  - Ramotion boldness
  - one clear focal move
  - more assertive crop
  - poster logic first
  - no extra product panels unless they improve the story

- **LinkedIn / LinkedIn feed**
  - MetaLab editorial framing
  - calmer hierarchy
  - more whitespace
  - more credible and less hype-driven

## Text rule

If the image model has a tendency to invent or rewrite text:
- use **zero text overlays** inside the generated asset
- compose headlines, case-study copy, and supporting labels **deterministically** outside the image model

Do not ask the image model to fabricate:
- case-study headlines
- subheads
- feature bullets
- product claims

## Non-interface social rule
If the social asset is logo-first or campaign-first rather than screenshot-first:
- preserve the real mark and approved brand motifs
- use one field, one emblematic move, and one message at most
- ban fake SaaS copy, fake product names, and random interface widgets

## Differentiation rule

When generating several social formats in one project:
- X portrait should feel like a mobile poster
- X landscape should feel like a campaign crop
- LinkedIn square should feel like a clean professional tile
- OG should feel like a universal link-preview frame

If two of those read as the same layout resized, rewrite the prompts before generating.

- **Square social**
  - Pentagram / Koto system clarity
  - one lockup-like composition
  - stronger border, field, or crop logic
  - no “one big card + one small card” by default
