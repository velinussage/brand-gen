---
name: brand-gen-logo
description: >
  Logo / wordmark / lockup workflow for brand-gen. Use this when the user is exploring marks,
  not standard product/social materials.
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Gen Logo

Use this instead of the main skill when the artifact is primarily a logo, wordmark, or lockup.

## When this is different

Logo work has different constraints than normal brand materials:
- fewer refs, more silhouette discipline
- stronger preference for vector/logo-friendly paths
- tighter human review loop between rounds

## Core flow

1. `python3 scripts/validate_setup.py`
2. Gather existing marks / sketches / inspiration into a dedicated folder.
3. Choose one mode:
   - `reference` — preserve recognizable structure
   - `inspiration` — net-new exploration
   - `hybrid` — preserve core equity while translating approved inspiration mechanics
4. Generate a small batch.
5. Review, score, and lock fragments.
6. Iterate only after the user clarifies what to keep and what to reject.

## Core commands

- `python3 mcp/logo_iterate.py generate ...`
- `python3 mcp/logo_iterate.py compare --top 5`
- `python3 mcp/logo_iterate.py feedback vN --score 4 --notes "..."`
- `python3 mcp/logo_iterate.py evolve`

## Gotchas

- Never fabricate a lockup unless a real wordmark/lockup asset exists.
- Favor short geometric prompt language.
- Stop after each batch so the user can choose what equity to preserve.
