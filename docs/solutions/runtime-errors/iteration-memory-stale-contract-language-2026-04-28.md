---
title: "Stale contract language reseeded from iteration memory across versions"
date: 2026-04-28
track: bug
category: runtime-errors
problem_type: memory-staleness
module: "brand_gen/sage_generation_contract.py, brand_gen/blackboard.py"
status: resolved
severity: high
related_files:
  - brand_gen/sage_generation_contract.py
  - brand_gen/blackboard.py
tags:
  - "iteration-memory"
  - "contract-repair"
  - "blackboard"
  - "stale-language"
  - "scratchpad"
---

## Problem

Sage plans accumulated stale "loom/thread/wardrobe/textile/closet" metaphors across versions v185-v188 even after those metaphors were explicitly banned upstream. Contamination persisted because old plan artifacts were reused as source traces, and positive-language fields (`adoption_scene`, `style_anchor`, `prompt_seed`) carried the old wording forward while only the negative `ban` list got updated. v192 (stinger) then reused stale screenshots as start frames and produced an incoherent "light bulb" metaphor scored 0/5. (session history)

## Symptoms

- Generated images still show woven/textile imagery after `"no thread/loom/wardrobe/textile/closet metaphor"` was added to bans.
- Plan JSON contains both `"ban": ["no thread/loom..."]` AND `"adoption_scene": "routing loom threads one reusable Behavior..."` — the positive scene contradicts the ban.
- Versions reseeded from cached scratchpads keep producing the banned imagery despite contract being correct in source.

## What didn't work

- **Adding more bans** — bans don't rewrite positive language.
- **Manually editing one plan version** — old plans are reused as source traces, so contamination re-enters.
- **Skipping the offending versions** — iteration memory carried the language forward through `capture_feedback_into_iteration_memory`.
- **Just changing the contract source** — was insufficient because old artifacts were already cached on disk in `.brand-gen/brands/sage/scratchpads/` and reseeded subsequent runs. (session history)

## Solution

`repair_stale_sage_contract_text()` and `repair_stale_sage_plan_contract()` in `brand_gen/sage_generation_contract.py` (~lines 250-375). Three-pass repair, run as a runtime guard before prompt assembly:

**1. Direct phrase replacement** (`_SAGE_STALE_POSITIVE_REPLACEMENTS`):

```python
("routing loom threads one reusable Behavior into a thin agent harness; "
 "the agent uses it as the default path to finish work",
 SAGE_SWITCHBOARD_ADOPTION_SCENE),
```

**2. Sentence-by-sentence rewrite** — splits text on sentence delimiters, skips sentences with negative-context terms (`no`, `do not`, `avoid`, `ban`, …), and rewrites stale terms only in *affirmative* sentences:

```python
if (not _is_negative_constraint_text(sentence)
        and any(term in lowered for term in _SAGE_STALE_POSITIVE_TERMS)):
    new_sentence = re.sub(r"\brouting loom\b", "switchboard/control-room routing grid",
                          new_sentence, flags=re.IGNORECASE)
    new_sentence = re.sub(r"\bwardrobe\b", "standard-library shelf",
                          new_sentence, flags=re.IGNORECASE)
    new_sentence = re.sub(r"\bthreads?\b", "routes",
                          new_sentence, flags=re.IGNORECASE)
```

**3. Plan-level field repair** (`repair_stale_sage_plan_contract`) — walks `prompt_seed`, `product_truth_expression`, `system_mechanic`, `purpose`, `target_surface`, `briefing`, `push`, `preserve`, and the nested `sage_generation_contract.adoption_scene`/`style_anchor`. Bans are merged and deduped, never rewritten. Records `sage_contract_repair.changed_fields` so the agent sees what was repaired.

## Why this works

Negative constraints and positive language live in different fields and need different treatment. The repair is deterministic, idempotent, and runs at scratchpad-generation time before prompt assembly — so cached artifacts get cleaned on next read. Sentence-level negation detection distinguishes "no thread metaphor" (keep) from "threads behavior into harness" (rewrite).

## Prevention

- When a metaphor or term gets banned, **also check positive references** in `prompt_seed` / `adoption_scene` / `style_anchor` / iteration memory. Rewrite them; don't just append a ban.
- Run sentence-level negation detection before mutating policy text.
- Surface `*_contract_repair.changed_fields` in agent output so contamination is visible to operators.
- Treat scratchpads in `.brand-gen/brands/<brand>/scratchpads/` as cache, not truth — old contract language can outlive the source change. (session history)

## Pattern signal

```
"ban":.*\["no X"...\] AND positive field contains \bX\b   # contradictory plan
SAGE_STALE_POSITIVE_TERMS / SAGE_STALE_POSITIVE_REPLACEMENTS  # stale-term registry pattern
re.sub.*\bold_term\b.*new_term                           # sentence-level term rewrite
```

If a contract change requires a re-render to take effect, the repair pass is missing or stale.
