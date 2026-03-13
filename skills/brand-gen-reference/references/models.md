# Brand-gen model guidance

Use this only when choosing a model or execution path.

## First choice by workflow

- `pipeline` is the default entrypoint for standard materials.
- Let the scratchpad choose the repo-default model unless the user asks for a specific backend.
- Use deterministic compose scripts when exact layout/copy control matters more than generative variation.

## Model comparison

### Image-oriented paths

| Model / path | Best for | Speed / cost shape | Notes |
|---|---|---|---|
| Repo default image path via `pipeline` | Browser illustration, social, hero/banner, feature still | Best default | Prefer this unless you have a concrete reason to override. |
| `google/nano-banana-2` | Reference-preserving and multi-reference edits | Medium | Strong when brand/product proof must stay recognizable. |
| `recraft-v4` / vector-oriented paths | Cleaner exploratory redraws, more logo-like or illustration-like stills | Medium | Better when pushing away from screenshot realism toward cleaner shapes. |
| Deterministic compose scripts | Posters, sticker sheets, exact copy layouts, controlled SVG/HTML | N/A | Not a model choice; use when exact composition matters more than stochastic variation. |

### Video / motion-oriented paths

| Model / path | Best for | Notes |
|---|---|---|
| Repo default motion path via `pipeline` | Feature animation, short product proof loops | Use when the user asks for motion but still wants brand-gen orchestration. |
| Motion-specific step-by-step flow | Debugging motion refs, pacing, or motion-only routing | Use when routing or execution details need inspection. |
| Deterministic still first, then motion | Most branded motion work | Still-before-motion remains the safer rule. |

## Selection heuristics

- **Need product truth preserved?** Bias toward the default pipeline image path or `nano-banana-2` style reference-preserving runs.
- **Need cleaner redraw / less screenshot feel?** Bias toward `recraft-v4`-style paths or a deterministic compose path.
- **Need exact headline/copy lockup?** Stop thinking in model terms and switch to deterministic composition.
- **Need a coordinated family of assets?** Use `plan-set` / `generate-set`, not a different model.

## Aspect ratio / prompt gotchas

- `google/nano-banana-2` rejects freeform ratios like `1.91:1`; use supported ratios such as `16:9`, `4:3`, `1:1`, or `4:5`.
- More than two refs on interface materials usually hurts composition quality.
- If the user cares about exact wording or layout, do not solve it with a “better model”; use deterministic composition.
- Prompt seeds for interface materials should stay under roughly **400 chars** because the pipeline already injects prelude, messaging, iteration memory, refs, and inspiration doctrine.

## When not to override the model

Do **not** reach for a model override first when the real problem is:
- weak messaging/copy
- missing product truth in the plan
- too many refs
- off-target mechanic selection
- session messaging not updated yet
