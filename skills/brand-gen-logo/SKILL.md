---
name: brand-gen-logo
description: >
  Logo, wordmark, and lockup workflow for brand-gen. Use instead of the main brand-gen skill
  when the artifact is primarily a mark — logos, wordmarks, lockups, icons, or symbol
  explorations. Triggers on: "design a logo", "explore marks", "wordmark", "lockup",
  "icon design", "logo exploration", "brand mark", "symbol design", "logo iteration",
  or any request focused on mark-making rather than standard brand materials. Don't use for
  social cards, illustrations, browser mockups, or content cards — those use the main
  brand-gen skill.
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Gen Logo

Use this instead of the main brand-gen skill when the artifact is primarily a logo, wordmark, or lockup. Logo work has different constraints than standard brand materials.

## How logo work differs

- **Fewer refs, more silhouette discipline** — logos need clean shape language, not reference-heavy compositions
- **Geometric prompt language** — say "flat vertical rectangles" not "columns"
- **Tighter review loops** — stop after each batch so the user chooses what equity to preserve
- **Fragment locking** — prompt fragments that work can be locked for all future generations
- **Vector-friendly models** — `recraft-v4` and `recraft-v4-svg` are preferred over photo-realistic models

## CLI and MCP tools

Logo has its own CLI and MCP server, separate from `bgen`:

- **CLI**: `python3 mcp/logo_iterate.py <command> [opts]`
- **MCP tools**: `logo_generate`, `logo_feedback`, `logo_show`, `logo_compare`, `logo_evolve`, `logo_bootstrap`, `logo_inspire`

## Core workflow

### 1. Bootstrap (first use only)

```bash
python3 mcp/logo_iterate.py bootstrap
```

MCP: `logo_bootstrap()` — scans existing logo files into the manifest.

### 2. Gather inspiration

```bash
python3 mcp/logo_iterate.py inspire symbol          # browse logosystem.co by category
python3 mcp/logo_iterate.py inspire --url <url>     # custom inspiration URL
python3 mcp/logo_iterate.py inspire symbol --list   # list saved inspiration
```

MCP: `logo_inspire(category="symbol")` or `logo_inspire(url="<url>")`

Categories: `symbol`, `wordmark`, `symbol-text`, `brown`, `beige`, `black`, `all`.

### 3. Choose a mode

- **`reference`** — preserve recognizable structure from existing mark
- **`inspiration`** — net-new exploration, no structural constraints
- **`hybrid`** — preserve core equity while translating approved inspiration mechanics

### 4. Generate a batch

```bash
python3 mcp/logo_iterate.py generate \
  -p "Geometric pillar mark, three flat vertical rectangles ascending left to right, warm copper on transparent, clean silhouette" \
  -m recraft-v4 \
  --aspect-ratio 1:1 \
  --tag icon \
  --mode inspiration
```

MCP: `logo_generate(prompt="...", model="recraft-v4", aspect_ratio="1:1", tag="icon", mode="inspiration")`

**Models for logo work:**

| Model | Best for |
|-------|---------|
| `recraft-v4` | Clean vector-style marks, sharp silhouettes |
| `recraft-v4-svg` | SVG output for true vector paths |
| `ideogram` | Text-heavy wordmarks, typography-first marks |
| `nano-banana-2` | Reference-preserving when iterating from an existing mark |

Pass reference images with `--reference-images /path/to/ref.png` or `--reference-dir /path/to/approved/`.

### 5. Review, score, and lock fragments

```bash
python3 mcp/logo_iterate.py feedback v12 --score 4 --notes "Strong silhouette, simplify left column"
python3 mcp/logo_iterate.py feedback v12 --status favorite
python3 mcp/logo_iterate.py feedback v12 --lock "three ascending rectangles" "warm copper"
```

MCP: `logo_feedback(version="v12", score=4, notes="...", lock_fragments=["three ascending rectangles"])`

**Locked fragments** persist into all future prompts. Use them to protect equity that works.

### 6. Compare versions

```bash
python3 mcp/logo_iterate.py compare v10 v11 v12    # specific versions
python3 mcp/logo_iterate.py compare --favorites     # all favorites
python3 mcp/logo_iterate.py compare --top 5         # top 5 by score
```

MCP: `logo_compare(versions=["v10","v11","v12"])` or `logo_compare(favorites=true)`

### 7. Evolve — learn from scored patterns

```bash
python3 mcp/logo_iterate.py evolve
```

MCP: `logo_evolve()` — analyzes prompt patterns across scored versions. Shows what works, what fails, locked fragments, and word frequency analysis.

### 8. Show manifest

```bash
python3 mcp/logo_iterate.py show              # full manifest
python3 mcp/logo_iterate.py show v12          # specific version detail
python3 mcp/logo_iterate.py show --favorites  # favorites only
python3 mcp/logo_iterate.py show --top 5      # top 5
```

MCP: `logo_show()` or `logo_show(version="v12")`

## Scoring (same as main brand-gen)

**5**=near-ship, **4**=good direction, **3**=mixed, **2**=weak, **1**=reject.

The agent can propose scores based on conversation, but only persist when user intent is explicit. Always stop after each batch so the user clarifies what to keep and what to reject.

## Shared brand context

Logo work benefits from the same brand foundation as standard materials. If a saved brand exists:

```bash
bgen show-session-summary --format json    # check current brand state
bgen show-identity --format json           # brand identity for tone/palette guidance
bgen ideate-messaging --format json        # messaging context for wordmark copy
```

Use the main brand-gen skill's identity and messaging to inform logo prompt language — tone words, palette direction, and shape language cues all apply.

## What to avoid

- Never fabricate a lockup unless a real wordmark/lockup asset exists
- Don't overload prompts with detail — logos need clean, geometric language
- Don't skip review between batches — the user must choose what equity to preserve before iterating
- Don't use photo-realistic models for mark exploration — prefer `recraft-v4` family
- Don't generate more than 3-5 versions before stopping for feedback
