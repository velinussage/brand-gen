---
name: brand-gen-truncation-audit
description: >
  Audit every prompt-truncation, compression, and lossy-slice site in the brand-gen Python
  package. Produces a manifest of every cap call (cap_text_at_sentence, compress_prompt_body,
  evict_to_budget, hard `[:N]` slice) with file:line, the limit value, the limit source
  (constant, JSON, hard-coded literal), and whether the drop is tracked (emits dropped_blocks
  / recommendation) or silent. Flags any cap that fires before the PromptBlock priority system.
  USE WHEN: assessing prompt fragility, before changing prompt budgets, when "the prompt feels
  truncated", planning a refactor of prompt_assembly.py, or auditing why high-priority blocks
  silently disappear.
  DO NOT USE WHEN: generating brand materials (use brand-gen-orchestration), changing what
  goes INTO a prompt (use brand-gen), or investigating model output quality (use the critic
  pipeline). This skill is read-only — it diagnoses, it does not edit.
compatibility:
  tools: [Bash, Read, Grep, Glob]
---

For Sage brand work in Pi, use the paste-ready prompt at `docs/prompts/pi-sage-brand-gen-full-pipeline.md`. Keep this link instead of copying the full prompt into skill bodies.

# Brand-Gen Truncation Audit

**Risk addressed:** prompt assembly applies caps through 6+ layers in sequence (per-part `cap_text_at_sentence` → joined-prelude cap → `compress_prompt_body` → `evict_to_budget` over `PromptBlock`s → execution-prompt re-cap → ad-hoc `[:N]` slices). Most truncation is **silent** — only `review_prompt_architecture` reports dropped blocks. Hard-coded limits live as magic numbers across 14+ files. The priority-tier `PromptBlock` machinery (`prompt_block.py`) only sees content **after** earlier caps already fired.

## What this skill produces

A single JSON-shaped manifest of cap sites. Each entry:

```json
{
  "site_id": "prompt_assembly.py:387",
  "kind": "cap_text_at_sentence | compress_prompt_body | evict_to_budget | hard_slice | summarize | strip",
  "stage": "per_part | combined_prelude | body | execution | post_block_eviction",
  "input_field": "brand_anchor_rule | inspiration_directive | copy_bank | …",
  "limit_value": 480,
  "limit_source": "constant:NON_INTERFACE_BODY_CAP | json:data/prompt_budget.json#interface | literal:480 | literal:[:5]",
  "configurable": true,
  "tracked": true,
  "tracked_via": "dropped_blocks | recommendation_string | none",
  "fires_before_priority_system": false,
  "snippet": "cap_text_at_sentence(brand_anchor_rule, NON_INTERFACE_BODY_CAP)"
}
```

Plus a summary: total sites, silent vs tracked ratio, sites firing before `evict_to_budget`, hard-coded literal counts by file.

## When to use

- Before adjusting `data/prompt_budget.json` — to know which caps actually respect it.
- Before promoting a new `PromptBlock` priority — to know which caps would defeat it.
- When `iteration_memory.json` keeps losing entries that the agent expected to survive.
- When the rendered prompt visibly drops a section the planner asked for but `dropped_blocks` is empty.
- When introducing a new prompt section, to choose where its cap should live.

## Inputs

- Repo path (default: `$PWD`, must contain `brand_gen/prompt_assembly.py`).
- Optional `--filter` — restrict to one of: `interface`, `non_interface`, `card`, `inspiration`, `copy`.
- Optional `--budget-source` — path to `data/prompt_budget.json` (default location auto-detected).

## Procedure

1. **Locate the cap primitives.** Read `brand_gen/prompt_assembly.py` for `cap_text_at_sentence`, `compress_prompt_body`, `_get_budget`, `_DEFAULT_BUDGET`. Read `brand_gen/prompt_block.py` for `evict_to_budget`, `SECTION_PRIORITY`, `SECTION_STAGE`, `SECTION_CONSTRAINT`. Read `brand_gen/card_text.py` for `_truncate_multiline_copy`. Note the function signatures and what each emits as side-effect (returned struct, appended `dropped_blocks`, logged warning, silent).

2. **Enumerate every call site for each primitive.** Use Grep for the function names. For each match, capture file:line, the args, the surrounding stage label (per-part vs combined-prelude vs body vs post-block-eviction).

3. **Enumerate hard `[:N]` slices on prompt content.** Grep `prompt_assembly.py`, `reference_role_packs.py`, `inspiration_extraction.py`, `card_builder.py`, `card_engine.py`, `sage_generation_contract.py` for patterns: `\[:\d+\]`, `\[:[A-Z_]+\]`, `\.strip\(\)\[:`, `\.split[^]]*\)\[:`. Filter to those operating on prompt-bearing strings (skip list-of-Tuple slices for typed records).

4. **Enumerate raw character truncations.** Grep for `truncate`, `max_len`, `max_chars`, `summary`, `condense`, `[:1200]`, `[:2000]`, `…`. For card flows, capture `(max_lines, max_chars)` tuples in `card_engine.py:762,1158,1195,1224,1304`.

5. **Classify each site:**
   - **kind** — which primitive (or `hard_slice` for raw `[:N]`).
   - **stage** — read 30 lines of context to decide whether this fires inside `build_effective_prompt` per-part, combined-prelude, body-cap, after `evict_to_budget`, or inside the execution-prompt builder.
   - **limit_value, limit_source** — trace the constant. Resolve `NON_INTERFACE_BODY_CAP` etc. to its `_DEFAULT_BUDGET` entry and check whether `data/prompt_budget.json` overrides it.
   - **tracked** — does the output struct of the enclosing function include the drop? Check `review_prompt_architecture` (`prompt_assembly.py:1391-1560`) for what gets added to `dropped_blocks` / `recommendations`. Anything outside that surface is silent.
   - **fires_before_priority_system** — true if it executes before `evict_to_budget(blocks_from_sections(...), budget)` runs in `build_execution_prompt`. Per-part caps in `build_effective_prompt` are ALL true.

6. **Cross-check against `SECTION_PRIORITY`.** For each tracked section name in `prompt_block.py`, list every cap that could touch its content before the priority system gets to weigh it. A `brand_anchor_rule` (priority 0, hard) silently truncated by a per-part `[:N]` is the highest-severity finding.

7. **Emit manifest.** Format as JSON to stdout (or `--output <path>`). Print summary table:
   - Total sites, silent count, tracked count.
   - Sites firing before priority system, by section name.
   - Hard-coded literal limits (count + file).
   - Sites operating on hard-constraint sections (worst risk).

## Output schema

```json
{
  "summary": {
    "total_sites": 142,
    "silent": 118,
    "tracked": 24,
    "fires_before_priority_system": 87,
    "hard_section_silent_caps": 11,
    "files_with_literal_limits": 14
  },
  "sites": [ /* entries shaped like the example above */ ],
  "section_coverage": {
    "brand_anchor_rule": { "priority": 0, "constraint": "hard", "pre_priority_caps": 3, "tracked_caps": 1 }
  },
  "duplicate_primitives": [
    { "primitive": "sentence-aware truncation", "implementations": ["prompt_assembly.cap_text_at_sentence", "card_text._truncate_multiline_copy"] }
  ]
}
```

## Reference files

- `brand_gen/prompt_assembly.py` (lines 387-425, 1391-1560) — compression hot zone.
- `brand_gen/prompt_block.py` — priority/eviction model, the source of truth this audit verifies.
- `brand_gen/card_engine.py` (lines 762, 1158, 1195, 1224, 1304) — card-side truncation regime.
- `brand_gen/card_text.py:660` — duplicate `_truncate_multiline_copy`.
- `data/prompt_budget.json` — externalized limits; verify which caps actually read it.

## Don't

- Don't propose fixes inside this skill. The output feeds `brand-gen-architecture-pass` orchestrator and `compound-engineering:ce-plan` for remediation planning.
- Don't edit prompt_assembly.py while running this audit — the manifest is a snapshot.
- Don't conflate `[:N]` on a List of typed records (fine) with `[:N]` on prompt content (lossy).
