---
title: "entity_type=prompt fallback collapses share-card outputs to detail_matrix"
date: 2026-04-28
track: bug
category: logic-errors
problem_type: routing-fallback-masks-intent
module: brand_gen/route_predicates.py
status: open
severity: high
related_files:
  - brand_gen/route_predicates.py
  - data/workflow_router_rules.json
  - brand_gen/card_builder.py
  - brand_gen/card_engine.py
tags:
  - "routing"
  - "share-card"
  - "entity-type"
  - "composition-family"
  - "fallback-default"
---

## Problem

`_infer_entity_type()` in `brand_gen/card_builder.py` defaults missing/no-source URLs to `"artifact"`, but downstream layout selection in `brand_gen/card_engine.py` treats the {prompt, skill, library} cluster as a single layout family. When `entity_type` is inferred as `"prompt"` (the most common path-segment match), every share card without explicit proof content renders the same `prompt-detail-matrix` layout — visually identical cards across genuinely different content.

Concrete trace (Apr 27): v162 (proof-poster, run `bc892270cc2e`), v163 (editorial-card, `107e9cd2fc13`), v166 (social, `4a529a2fb685`) all ended in `composition_family: detail_matrix` because no `source_url` was provided, so each defaulted to `entity_type=prompt`, then Sage's prompt share-card template forced `editorial_poster + detail_matrix`. Three intents collapsed to one layout. (session history)

## Symptoms

- Multiple share cards (announcement, social, content-card) all collapse to the same 2-column proof-on-right layout.
- `default_layout_spec` returns identical `LayoutSpec(columns=2, ..., proof_style="document", canvas_preset="document")` for every announcement-card with `entity_type in {"prompt", "skill", "library"}`.
- `_render_entity_detail_html(card, variant="matrix")` fires regardless of whether the card has structured `detail_blocks`.
- Sage custom scratchpad says "share-card flow is retired" but runtime keeps using it — the retirement was prompt guidance, not enforced. (session history)
- v166 bypassed a blocking learning warning and generated anyway — bypass logic too lenient.

## What didn't work

- **Adding more entity types** — they all collapsed to the same `{prompt, skill, library}` group at layout time.
- **Distinguishing `prompt` from `skill` in CSS** — the same `_render_prompt_detail_html` rendered both.
- **Updating prompt scratchpad guidance** ("share-card retired") — guidance was not enforced at runtime; the share-card path still fired.

## Solution (partial — open)

The card_builder code now uses several distinguishing signals before falling through to the prompt detail matrix:

**1. Entity-specific defaults** (`_default_proof_meta`, `_default_proof_excerpt` in `card_builder.py`) so the proof crop varies even when source is missing.

**2. Body-content discrimination** (`_material_default_strategy`):

```python
if "prompt" in blob:
    ...
if all(token in blob for token in ("prompt", "skill")):
    ...
```

Brand share templates now check the prompt body content instead of relying on `entity_type` alone — no-source social/editorial/proof requests don't all become the same prompt-detail card.

**3. Layout dispatch tightening** (`card_engine.py:301`) restricts the document-style layout strictly to:

```python
material_type == "announcement-card" AND entity_type in {prompt, skill, library}
```

Other materials fall through to portrait single-column.

**4. QR-vs-proof-crop split** — `entity_type in {prompt, skill, library}` triggers a QR code, suppressing the proof crop image. Makes prompt/skill/library cards visually distinct from generic artifact cards.

## Why this works

The fix decouples `entity_type` (what kind of source object) from layout family (what visual shape). Layout dispatch now needs both `material_type` and `entity_type` to agree before locking in `detail_matrix`; missing-proof situations fall through to defaults that vary by entity type rather than collapsing to one layout.

## Prevention

- **Inference functions that fall through to a default should never be the only discriminator for visual layout.** `_infer_entity_type → "artifact"` is a reasonable inference, but it cannot also select a layout family by itself.
- **Layout selection should require positive signals** — real `source_url`, real `detail_blocks`, named `material_type` — not the absence of negative ones.
- When the user reports "everything looks the same," check the discrimination chain. Usually one signal is doing all the work and a missing input collapses many cases.
- Make scratchpad-level "retired" claims enforceable at runtime, not just in prompt prose. Enforce via route predicates / workflow router rules. (session history)
- Audit all `bypass_*` flags in the run ledger; v166 generated despite a blocking learning warning. (session history)

## Pattern signal

```
entity_type in {"prompt", "skill", "library"}    # cluster treated as one
return "prompt"   /  default = "prompt"           # too-eager fallback
LayoutSpec\(.*canvas_preset="document"            # one layout for many materials
_render_prompt_detail_html.*variant="matrix"      # matrix variant fires regardless of content
composition_family.*detail_matrix                 # if seen for 3+ different intents → collapse
```

Trace `composition_family` across recent runs in the run ledger. If three different `material_type` values produce the same `composition_family`, the routing is collapsing.
