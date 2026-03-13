# Product Presentation Reference Brief

Use this before generating any screenshot-derived browser illustration, banner, social card, or feed visual.

## Core rule

Separate **product truth** from **presentation reference**.

- **Product truth** = the real screenshots of the app you must preserve
- **Presentation reference** = external examples that define crop, framing, whitespace, background, and polish

Never use the real app screenshots as the only style target.

## Workflow

1. Capture the real product screens first.
2. Find 3–5 external presentation references from official product/marketing pages or the curated brand-example source registry.
3. Write down exactly what to borrow from each reference:
   - browser chrome or no browser chrome
   - crop style
   - amount of whitespace
   - background treatment
   - shadow / depth level
   - copy density
4. Explicitly state what must **not** be borrowed:
   - product UI structure
   - product copy
   - buttons / cards / labels
   - fake features
5. Write the generation prompt so the app screenshot is the hero asset and the external references only influence presentation.

## Agency compare gate

Before each batch, explicitly answer:

1. **What is the single hero product moment?**
   - one real screen or one real crop only
2. **What gets removed?**
   - extra panels
   - redundant sidebars
   - synthetic browser chrome
   - decorative clutter
3. **Which stance is this batch using?**
   - **Ramotion boldness** = stronger focal move, fewer but larger surfaces
   - **MetaLab editorial framing** = more whitespace, calmer hierarchy, more credibility
4. **How many supporting surfaces are allowed?**
   - default: one inset maximum

If you cannot answer those four things, the prompt is still too loose.

## Anti-convergence gate

Before generating multiple material types, answer these too:

1. **What is this asset's job?**
   - browser illustration
   - banner
   - social poster
   - styleframe
2. **What changes visually from the last asset?**
   - crop depth
   - background / field
   - frame style
   - inset count
   - perspective
   - graphic device
3. **What should be removed because it belongs to another material type?**
   - browser chrome
   - support inset
   - large UI heading
   - soft editorial whitespace
   - poster-like boldness

If you cannot name at least 3 visible differences between two planned outputs, they will converge.

## Non-negotiable rules for screenshot-derived visuals

- Do **not** redesign the UI unless the user explicitly asks for a redesign.
- Do **not** invent product copy, features, labels, cards, buttons, or metrics.
- Do **not** add decorative complexity that makes the UI less clear.
- Prefer one clear product story per visual.
- Crop to the strongest real product component instead of showing the whole app window by default.
- If text inside the UI becomes unreadable, simplify the crop rather than rewriting the product.
- Do not solve weak composition by adding more UI.
- Default to one hero window and one supporting inset maximum.
- On the next round, subtract before you decorate.
- Do not let every output collapse into the same warm-neutral floating-card system.
- The brand field, crop, and frame should change with the material type.
- If the real UI heading starts acting like the marketing headline, crop deeper into the product content.

## Good official references

- Cursor features — subtle background + real UI as hero  
  https://cursor.com/features
- Linear homepage — one clear workflow story per product visual  
  https://linear.app/homepage
- Raycast browser extension — clean framing and whitespace around real product UI  
  https://www.raycast.com/browser-extension
- Vercel integration image guidelines — real product glimpse, avoid full-window screenshots, highlight the most compelling component  
  https://vercel.com/docs/integrations/create-integration/integration-image-guidelines

## Agency stance cheat sheet

Use these as named prompt anchors when you want sharper art direction:

- **Ramotion**
  - bold focal move
  - fewer, larger surfaces
  - strong scale contrast
- **MetaLab**
  - editorial framing
  - quieter hierarchy
  - credibility through restraint
- **Gretel**
  - type-first pacing
  - controlled brand attitude
  - sharper campaign discipline
- **BUCK**
  - flexible brand system thinking
  - cleaner shape language
  - stronger motion-readiness
- **PORTO ROCHA**
  - graphic confidence
  - stronger contrast and visual identity
  - more ownable brand field
- **Wolff Olins**
  - ecosystem-level clarity
  - stronger narrative frame
  - more platform confidence
- **Pentagram**
  - coherent multi-surface identity
  - disciplined composition
  - strong visual system logic
- **Mother Design**
  - story-led framing
  - more verbal point of view
  - stronger campaign energy

Do not ask the model to imitate an agency wholesale.
Instead specify:
- which agency controls **scale**
- which agency controls **framing**
- which agency controls **brand attitude**

## Curated source registry

You can also search and capture categorized references from:
- `data/brand_example_sources.json`
- `prompts/brand-example-source-strategy.md`

Use the category folders to build reusable reference libraries for:
- SaaS/product presentation
- premium branding
- broader studio exploration

Also follow:
- `prompts/material-type-differentiation.md`

## Prompt pattern

```text
Use the real product screenshot as the central visual asset. Focus on one exact approved product moment. Do not redesign the UI. Preserve the actual interface structure and labels. Borrow only the presentation qualities from the external references: Ramotion boldness in focal scale and clarity, MetaLab editorial framing in negative space and hierarchy, plus crop discipline, browser framing, subtle depth, and background treatment. Use one hero window and one inset maximum. Keep the result launch-ready, readable, and minimally decorated.
```

## X / feed variation

```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Reframe it for a feed-safe composition with stronger focal crop, safe margins, and minimal or no text overlays. Use Ramotion boldness for the main focal move and MetaLab editorial restraint for the surrounding space. One hero window, one inset maximum. Borrow only the presentation treatment from the external references, not their UI or copy.
```

## Structural reset rule

Hard-ban reuse of prior layout skeletons when a new material type is supposed to feel different.
If the last result used a centered floating card with one small inset, start from a different structure before styling.
