---
title: "Prompt compression drops high-priority blocks before priority sort"
date: 2026-04-28
track: bug
category: logic-errors
problem_type: intent-loss-on-compression
module: brand_gen/prompt_assembly.py
status: open
severity: high
related_files:
  - brand_gen/prompt_assembly.py
  - brand_gen/prompt_block.py
tags:
  - "prompt-assembly"
  - "compression"
  - "priority-sort"
  - "intent-loss"
  - "cap-text"
---

## Problem

`brand_gen/prompt_assembly.py` has 6+ independent `cap_text_at_sentence` call sites (lines 222, 343, 389, 425, 1463, 1478) and a downstream `compress_prompt_body` + `evict_to_budget`. Several caps fire **before** the PromptBlock priority sort runs, so high-priority blocks (product-truth contract, recent feedback, selected inspiration) get truncated mid-sentence by a per-section cap before the priority system has a chance to drop low-priority prose instead.

## Symptoms

- Generation prompts lose the back half of `selected_inspiration_block` or `role_pack_block` while keeping low-signal `material_policy` prose.
- "Body" creative direction gets compressed even when the prelude is already short.
- `dropped_blocks` recommendation surfaces blocks that were already partially capped.
- Generated images go generic, especially when `source_url` / proof is absent — root signal got truncated, fallback templates fired.

## What didn't work

- **Single global cap** — interface vs non-interface materials need different budgets.
- **Per-section caps without a priority sort** — high-value blocks lost text first because they appeared late in the order.
- **Capping body before prelude** — creative direction is the highest-signal content; capping it first is exactly backward.
- **Local fix per block type** (Apr 26 partial pass) — moving Sage product-truth into structured metadata helped one block but didn't solve the underlying pre-priority truncation. (session history)

## Solution

Two-layer system in `prompt_assembly.py`. **Layer 2 is the durable fix; Layer 1 is a stopgap.**

**Layer 1 — per-part caps** (lines 388-399, 1463) shrink obviously verbose sections only:

```python
if material_key not in INTERFACE_MATERIAL_KEYS:
    brand_prelude = cap_text_at_sentence(brand_prelude, NON_INTERFACE_PRELUDE_CAP)
    doctrine = cap_text_at_sentence(doctrine, NON_INTERFACE_DOCTRINE_CAP)
    reference_analysis_snippet = cap_text_at_sentence(reference_analysis_snippet, NON_INTERFACE_REF_ANALYSIS_CAP)
```

**Layer 2 — body-first priority eviction** (lines 1494-1501):

```python
total_cap = NON_INTERFACE_TOTAL_PRELUDE_CAP if material_key not in INTERFACE_MATERIAL_KEYS else 2000
prelude_budget = max(total_cap - len(compact_body) - 4, int(total_cap * 0.3))
if len(prelude) > prelude_budget:
    kept_blocks, dropped_blocks = evict_to_budget(prompt_blocks, prelude_budget)
```

Body gets ≥40% of the total budget. `evict_to_budget` (in `prompt_block.py`) drops *whole blocks* by priority tier rather than mid-sentence truncation. `SECTION_PRIORITY` gives reference/inspiration blocks priority 8-12 (kept longer) and `material_policy` priority 30 / `reference_analysis_caveat` priority 80 (dropped first). Hard-constraint blocks (`brand_anchor_rule`, `sage_generation_contract`, `product_truth_contract`) cannot be evicted.

## Why this works

Image-model prompts are budget-sensitive and compression is silent by default. Without priority eviction, the pipeline degrades the highest-signal content (concrete reference styles) while preserving redundant policy prose. Recommendation surfacing (`recommendations.append(...)` lines 1520-1531) makes the loss visible to the agent so it can shorten the body itself.

## Prevention

- Never apply unconditional `text[:N]` slicing in front of a priority-aware compressor. Either tag every cap site as "after priority sort" or remove it.
- When you have a hard total length budget, drop low-priority guardrail prose; never truncate the user's creative input first.
- Surface what was dropped to the agent — silent loss compounds into "why is the output generic" complaints (which recurred 3+ times in the Apr 26-28 sessions). (session history)
- **Open work**: Audit every cap site — there are 6+ in `prompt_assembly.py`. The Apr 28 architecture audit named this risk #2; `brand-gen-truncation-audit` skill exists but the audit itself has not been run. (session history)

## Pattern signal

```
cap_text_at_sentence\(.*, [0-9]+\)        # multiple cap sites without coordination
text\[:N\]\.rstrip\(\) \+ "…"              # mid-sentence truncation
if len\(combined\) > MAX:                  # single global cap with no priority logic
```

If a cap site is upstream of the call to `evict_to_budget`, it's pre-priority and suspect. If your generated content goes generic when the brief is dense, suspect this class first.
