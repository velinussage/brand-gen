# Brand Concept Exploration

Use this as **phase 1** before collecting examples or spending generation credits.

## Goal

Turn a business or product brief into:
- 3–5 plausible brand directions
- recommended source packs to capture
- prompt seeds for the first browser illustration, social image, or banner

## Core rule

Do not jump straight from “make a feature visual” to generation.

First decide:
1. what story the product should tell
2. what visual direction best expresses that story
3. which outside references should influence presentation

## Inputs

- brand / product name
- business summary
- audience
- tone words
- avoid words
- product context
- desired materials
- optional extracted `brand-profile.json`

## Output

For each direction, produce:
- title
- why it fits
- what to show
- what to avoid
- best source sites to capture
- prompt seeds for the target materials

## Direction patterns

Useful starting directions:
- curated intelligence feed
- calm governed network
- approachable startup utility
- editorial trust layer
- living agent activity system

## Decision rule

Pick **one primary direction** and optionally borrow presentation discipline from a secondary one.

Example:
- primary = curated intelligence feed
- secondary = calm governed network

That means:
- the product story is activity + curation
- the presentation is calmer, more trustworthy, and less noisy

## Prompt-writing rule

The direction defines:
- story
- composition
- reference search strategy

The screenshots still define:
- actual UI
- real labels
- product truth

## Operational command

```bash
python3 mcp/brand_iterate.py explore-brand \
  --brand-name "Acme" \
  --business "Governed skill network for AI agents" \
  --audience "AI builders, power users, and communities" \
  --tone "trustworthy, active, approachable, light, curiosity-inducing" \
  --avoid "generic SaaS, too technical, crypto casino, fake UI redesign" \
  --product-context "logged-in app views: home feed, prompt detail, library/community" \
  --material browser-illustration \
  --material x-feed
```
