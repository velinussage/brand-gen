# Concepts

## Saved brands vs testing sessions

A **saved brand** is durable brand memory under `.brand-gen/brands/<brand>/`.

A **testing session** is a sandboxed workspace under `.brand-gen/sessions/<session>/brand-materials/` that can explore directions without mutating the saved brand immediately.

## Brand truth vs presentation truth

Keep actual brand anchors and product truth stable. Let references teach framing, hierarchy, pacing, and finish.

## Material sets

A set is a coordinated family of materials with different jobs, such as:

- hero
- product proof visual
- social card
- motion bumper
- supporting pattern system

Use `plan-set` / `validate-set` / `generate-set` when the request is really a family, not a single asset.

## Reference-role packs

References are grouped by role so the runtime can translate inspiration into intent instead of copying surfaces blindly.

Common roles:

- composition
- motif
- application
- motion

## Blackboard vs iteration memory vs journal

These surfaces serve different purposes:

- **blackboard** = current brief, decisions, active pointers, guardrails
- **iteration memory** = positive/negative examples and material-specific notes
- **journal / run logs** = operational trace of what actually ran

## Messaging before imagery

For copy-bearing materials, establish messaging and copy before asking the image model to render the surface.

## Structured share cards

Governed/source-derived share cards now use the HTML renderer plus card-data plugins. The output is deterministic layout + PNG rendering, not a freeform image-model card prompt.
