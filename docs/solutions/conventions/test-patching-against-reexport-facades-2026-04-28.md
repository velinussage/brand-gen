---
title: "Patches against re-export facade modules silently no-op"
date: 2026-04-28
track: knowledge
category: conventions
problem_type: test-patching-target
module: "brand_gen/material_planning.py, brand_gen/share_card_renderer.py"
status: documented
severity: medium
related_files:
  - brand_gen/material_planning.py
  - brand_gen/share_card_renderer.py
  - brand_gen/plan_builder.py
  - brand_gen/card_builder.py
  - brand_gen/html_share_cards.py
tags:
  - "testing"
  - "mock-patching"
  - "facade-pattern"
  - "module-split"
  - "conventions"
---

## Context

`brand_gen/material_planning.py` and `brand_gen/share_card_renderer.py` are re-export facades that wildcard-import from focused modules:

- `material_planning.py` (~28 lines) re-exports from `brand_policy.py`, `plan_builder.py`, `plan_validation.py`, `prompt_assembly.py`, `reference_role_packs.py`.
- `share_card_renderer.py` (~65 lines) re-exports from `card_text.py`, `card_engine.py`, `card_builder.py`, `card_plugins/*`.

All `from .material_planning import X` statements still work. But `unittest.mock.patch("brand_gen.material_planning.foo")` patches the **facade attribute**, not the actual function in the focused module. Tests pass silently while production code is unchanged.

This pattern recurred at least 3 times during recent module splits (`material_planning`, `share_card_renderer`, `html_share_cards`). The dangerous signature is **silent no-op patch + tests still green via cached real behavior**. (session history)

## Guidance

Target the module where the function is **defined**, not the facade.

```python
# WRONG — silently no-ops because plan_builder.create_material_plan
# imports get_brand_gen_dir directly, bypassing the facade
patch("brand_gen.material_planning.get_brand_gen_dir", return_value=...)

# RIGHT — patches the actual symbol the caller resolves
patch("brand_gen.plan_builder.get_brand_gen_dir", return_value=...)
patch("brand_gen.card_builder.validate_brand_workspace_dir", ...)
patch("brand_gen.html_share_cards.validate_brand_workspace_dir", ...)
```

Examples in the actual test suite (`tests/test_orchestration_api.py:142`, `tests/test_prompt_updates.py:326-528`):

```python
patch("brand_gen.plan_builder.check_identity_freshness", ...)
patch("brand_gen.plan_builder.get_brand_gen_dir", ...)
patch("brand_gen.plan_builder.save_plan_draft", ...)
```

## Why this matters

`from .X import *` rebinds names *into* the facade module's namespace, but the focused module's own internal calls (`get_brand_gen_dir(...)` inside `plan_builder.create_material_plan`) resolve through `plan_builder`'s globals, not the facade's. Patching the facade attribute leaves the production code path untouched, the test "passes" (no exception raised), and you ship a regression that's invisible in CI.

## When to apply

- Any test against code in a re-export facade pattern.
- Any time you split a large module into focused sub-modules — go through *all* tests and rewrite patch targets to the new location.
- Any new module that starts with a docstring like `"""...re-export facade..."""` is a patching hazard; document it in the facade module's docstring.

## Examples

From the project's auto-memory:

> **Test patching**: patches must target the actual module (e.g., `mcp.plan_builder.get_brand_gen_dir`, not `mcp.material_planning.get_brand_gen_dir`).
>
> **Test patching**: patches must target the actual module (e.g., `mcp.card_builder.validate_brand_workspace_dir`, not `mcp.share_card_renderer.validate_brand_workspace_dir`).
>
> **Test patching**: `validate_brand_workspace_dir` must be patched at `mcp.html_share_cards.validate_brand_workspace_dir`.

(MEMORY.md auto memory [claude])

## Pattern signal

```
patch\("brand_gen\.material_planning\.       # likely wrong (facade)
patch\("brand_gen\.share_card_renderer\.     # likely wrong (facade)
"""...re-export facade..."""                  # docstring marker on facade modules
from \.X import \*                            # wildcard re-export
```

If a `patch()` target is on a module whose source file is under ~50 lines and starts with "re-export facade", it's almost certainly wrong. Look up where the symbol is *defined*, not where it's *re-exported*.
