# Polish and review format — Emil Kowalski's design-engineering applied to brand-gen

The installed `emil-design-eng` skill (`.agents/skills/emil-design-eng/SKILL.md`) is mostly about CSS animation, spring physics, Framer Motion, and React micro-interactions. Brand-gen generates **static images** and **AI video** via generative models — most of the skill's 700 lines don't map to prompt engineering.

**What actually applies to brand-gen:** two narrow surfaces.

---

## 1. HTML share cards (`brand_gen/card_engine.py`)

This is the only place brand-gen ships real CSS. The `html_taste_directives` and `html_design_engineering` blocks in `data/prompt_fragments.json` encode the emil-style rules (warm-tinted shadows, concentric radii, asymmetric enter/exit timing, transform+opacity-only, `prefers-reduced-motion` fallback, no `transition: all`, no `scale(0)` entry).

If you hand-code CSS around a share card — a landing page, a hero overlay, an interactive chrome element on top of the generated still — load the full `emil-design-eng` skill. The rules about spring physics, `@starting-style`, pointer capture, clip-path, and Framer Motion caveats are directly useful there.

If you're just writing prompts to a generative model, skip the full skill. The `motion_rules` / `motion_anti_patterns` arrays in `prompt_fragments.json` are the curated subset the card renderer will consume.

---

## 2. Brand-critic review format (Before / After / Why)

Emil's review output is a markdown table:

| Before | After | Why |
| --- | --- | --- |
| Quoted specific defect from the output | Concrete fix the next iteration should ship | One-sentence reason, citing a rubric axis or slop pattern |

The brand-critic already uses this shape programmatically as `before_after_diffs` in the critique JSON (see `.claude/agents/brand-critic.md` v2 output contract). Every row becomes a `--ban` / `--push` directive the planner feeds into the next run.

When the critic writes a human-readable narrative (post-run summary, Slack-style paste), use the same table format instead of free prose bullets. One row per issue. The "Why" column names the rubric axis (composition / brand_coherence / restraint / story_fidelity / meaning_clarity) plus the material overlay or disqualifier if any.

Free prose is for the **one-paragraph overall read** at the top ("what works, what fails overall"). Every individual fix goes in the table.

---

## Taste principles (apply to every material, not just CSS)

A few emil principles DO generalize beyond CSS — they're about how the critic and philosopher *think*, not about animation timing:

- **Unseen details compound.** A failed output is rarely one catastrophic error; it's a cluster of small tells. Flag the aggregate.
- **Beauty is leverage.** Good defaults matter more than options. A material's first-try output should already be excellent — variance is for iteration, not the default.
- **Cohesion matters.** Motion (if any) should match brand mood. Sage is editorial; its motion grammar should feel elegant, not reactive. The philosopher owns this via the motion-grammar block in `custom-scratchpad.md`.

These are already embedded in the rubric v2 (`meaning_clarity`, `restraint`, `brand_coherence`) — the emil skill is a useful-but-optional framing, not a new contract.

---

## When to load the full `emil-design-eng` skill

Load it when:
- Hand-coding CSS / React around a brand-gen asset (real animation, real component, real micro-interaction).
- Debugging "why does this HTML share card feel off?" at the CSS level.
- Writing reusable components that consume brand-gen design tokens.

Skip it for:
- Flux / Recraft / Seedance prompt engineering. These models don't speak CSS.
- Brand-critic image critique of static material. The rubric axes + AI Slop Check + `before_after_diffs` are the operative contract.
- Cinematographer Seedance prompts. The seven-rule validation in `seedance-shot-design.md` is the operative contract; emil's CSS easing rules don't translate.

---

## Related references
- [Design tokens](./design-tokens.md) — WCAG-audited palette / typography / spacing that the HTML share card consumes.
- [Seedance shot design](./seedance-shot-design.md) — cinematographer's motion-grammar and validation rules (applicable to video, NOT emil-adjacent).
- [`.agents/skills/emil-design-eng/SKILL.md`](../../../.agents/skills/emil-design-eng/SKILL.md) — the full upstream skill.
