---
name: brand-gen-reference
description: >
  On-demand reference pack for brand-gen. Load this only when you need model guidance, social
  surface specs, workspace file layout, or exact file/command gotchas.
compatibility:
  tools: [Read]
---

# Brand Gen Reference

This skill is reference data, not workflow doctrine.

## Load these files only when needed

- `references/models.md` — model guidance and when to pick each backend
- `references/social-surfaces.md` — X / LinkedIn / OG surface guidance
- `references/file-layout.md` — where session, brand, manifest, blackboard, and scratchpad files live

## Quick rules

- Need a model or aspect-ratio choice? Read `references/models.md`.
- Need exact surface dimensions or feed context? Read `references/social-surfaces.md`.
- Need to know where artifacts land on disk? Read `references/file-layout.md`.
- Need live data instead of a static note? Prefer commands:
  - `python3 mcp/brand_iterate.py social-specs`
  - `python3 mcp/brand_iterate.py show-session-summary --format json`
  - `python3 mcp/brand_iterate.py show-reference-analysis --format json`
