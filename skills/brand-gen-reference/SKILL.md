---
name: brand-gen-reference
description: >
  On-demand reference pack for brand-gen. Load this when you need model selection guidance,
  social/feed platform dimensions, workspace file layout, or aspect ratio gotchas. Use when
  the agent needs to choose between models, pick the right image dimensions for a platform,
  understand where files live on disk, or debug aspect ratio / prompt length issues. Triggers
  on: "which model", "what size", "what dimensions", "aspect ratio", "where are the files",
  "file layout", "workspace structure", "social specs", "feed dimensions", or when the agent
  is making model/surface/layout decisions during generation.
compatibility:
  tools: [Read]
---

# Brand Gen Reference

## Pi / Sage full-pipeline prompt

For Sage brand work in Pi, use the paste-ready prompt at `docs/prompts/pi-sage-brand-gen-full-pipeline.md`. It routes Pi through the typed `brand_*` tools, the `brand-orchestrator` subagent, exact-text gates, v2/DSPy review, GEPA-ready disagreement fields, and typed mutation loops. Keep this link instead of copying the full prompt into skill bodies.

Reference data for brand-gen — not workflow doctrine. Load individual reference files only when you need them.

Preferred CLI: `bgen ...` or `python3 -m brand_gen ...`

## Reference files

- **`references/models.md`** — model comparison, selection heuristics, and when NOT to override. Read when choosing a model or debugging generation quality.
- **`references/social-surfaces.md`** — X / LinkedIn / OG / podcast surface dimensions, composition notes, and copy/messaging rules. Read when picking dimensions for a platform.
- **`references/file-layout.md`** — where session, brand, manifest, blackboard, and scratchpad files live on disk. Read when locating artifacts.

## Quick decision shortcuts

- **Need a model or aspect-ratio choice?** Read `references/models.md`.
- **Model fails on an aspect ratio?** Not all models support all ARs. `og-card` (1.91:1) and `x-card` (2:1) require models that accept those ratios. Check `bgen types` for the default model per type. If the default model fails, try `recraft-v4` (widest AR support) or `nano-banana-2`.
- **Need exact surface dimensions or feed context?** Read `references/social-surfaces.md`, or run `bgen social-specs` for live data.
- **Need to find where artifacts land on disk?** Read `references/file-layout.md`, or run `bgen show-session-summary --format json`.
- **Need current reference analysis?** Run `bgen show-reference-analysis --format json`.
