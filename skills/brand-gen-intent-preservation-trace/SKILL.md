---
name: brand-gen-intent-preservation-trace
description: >
  For each typed MaterialPlan field, trace whether it survives as STRUCTURE (not
  flattened to free-text prose) into GenerationScratchpad, into the rubric scorer
  (BrandScorer.forward), and back into iteration memory. Identify the lossy
  boundaries where structured intent becomes a string nobody can re-parse. Output
  a field-survival matrix flagging fields that critique cannot reason about because
  they were stringified upstream.
  USE WHEN: planning a new MaterialPlan field, debugging "the critic ignored my
  constraint", before changing the scoring rubric, or assessing why
  iteration_memory entries lose specificity.
  DO NOT USE WHEN: auditing prompt size (use brand-gen-truncation-audit) or
  auditing namespace contracts (use brand-gen-phase-contract-audit). This skill
  is about semantic loss, not structural drift.
compatibility:
  tools: [Bash, Read, Grep, Glob]
---

# Brand-Gen Intent Preservation Trace

**Risk addressed:** `MaterialPlan` (`pipeline_types.py:72`) holds typed fields, but `create_material_plan` returns a dict, and `assemble_generation_scratchpad` reads via `plan.get("aesthetic_capsule")`, `plan.get("selected_inspiration_sources")`, `plan.get("system_mechanic")` etc. Many high-information fields are flattened to strings before generation: `selected_mechanic_labels` becomes `"borrow {a} and {b}; avoid {x}"` (`prompt_assembly.py:670`); `aesthetic_capsule` becomes free-form prose via `render_capsule_prompt`; `surface_strategy_candidates` is computed as a list but only the chosen `selected_surface_strategy_prompt_directive` string survives. Scoring (`scoring/program.py`) gets `brand_dna: str` and `story_objective: str` — the structured plan is gone.

**Once intent is a string, downstream stages cannot reason about *why* something was chosen.** Critique can only re-parse prose. Iteration memory captures `style_anchor` strings without the structured "this anchor came from variant X with score Y because Z." This caps the ceiling of the auto-feedback loop.

## What this skill produces

```json
{
  "summary": {
    "material_plan_fields_total": 28,
    "preserved_to_scratchpad": 14,
    "preserved_to_scorer": 5,
    "preserved_to_iteration_memory": 4,
    "lossy_boundaries": [
      "plan_builder → prompt_assembly (string render)",
      "scratchpad → scoring (only brand_dna/story_objective survive)",
      "any → iteration_memory (only style_anchor + score)"
    ]
  },
  "field_matrix": [
    {
      "plan_field": "aesthetic_capsule",
      "type": "dict",
      "scratchpad": "preserved_dict",
      "scorer": "lost — flattened to brand_dna prose",
      "iteration_memory": "lost",
      "string_render_site": "prompt_assembly.render_capsule_prompt:NNN",
      "consequence": "scorer cannot fault palette mismatch except via brand_dna prose; cannot suggest 'try alt capsule X'"
    },
    {
      "plan_field": "selected_mechanic_labels",
      "type": "list[str]",
      "scratchpad": "preserved_list",
      "scorer": "lost — joined as 'borrow X; avoid Y' string",
      "iteration_memory": "lost",
      "string_render_site": "prompt_assembly.py:670",
      "consequence": "iteration cannot promote a single mechanic; entire string treated atomically"
    },
    {
      "plan_field": "surface_strategy_candidates",
      "type": "list[dict]",
      "scratchpad": "lost — only selected_surface_strategy_prompt_directive (str) survives",
      "scorer": "lost",
      "iteration_memory": "lost",
      "string_render_site": "plan_builder.py:??",
      "consequence": "cannot A/B alternative strategies; rejection of selected has no structure to reuse"
    }
    /* ... per-field ... */
  ],
  "rubric_input_surface": {
    "scorer_signature_inputs": ["brand_dna", "story_objective", "rubric_axes"],
    "structured_plan_addressable": false,
    "minimum_extension": [
      "add aesthetic_capsule_id",
      "add selected_mechanic_ids: list[str]",
      "add inspiration_role_ids: list[str]",
      "add experiment_id (per brand-gen-experiment-modeling)"
    ]
  },
  "iteration_memory_surface": {
    "fields_persisted": ["version_id", "score", "style_anchor", "notes"],
    "structured_intent_persisted": false,
    "minimum_extension": ["plan_id", "selected_mechanic_ids", "aesthetic_capsule_id"]
  }
}
```

## When to use

- Before adding a new MaterialPlan field — verify it will reach the critic before claiming "the critic enforces this."
- When the agent reports "I added the constraint but it had no effect."
- Before extending the rubric — to know what input surface scoring actually has.
- Before claiming the auto-feedback loop is closed.

## Inputs

- Repo path (default `$PWD`).
- Optional `--field <name>` — trace one field end-to-end with snippet at each stage.

## Procedure

1. **Enumerate MaterialPlan fields.** Read `brand_gen/pipeline_types.py` `MaterialPlan` dataclass. Capture every field name + type. Also enumerate dict keys actually written by `create_material_plan` (`brand_gen/plan_builder.py`) — some keys are dict-only and don't appear in the dataclass.

2. **Trace each field forward to scratchpad.** Read `brand_gen/generation_flow.py` `assemble_generation_scratchpad` (line 329). For each plan field, locate its consumption: `plan.get("X")`, `plan["X"]`, or via merge. Tag as `preserved_dict`, `preserved_list`, `preserved_scalar`, `flattened_to_string`, or `dropped`.

3. **Find the string-render sites.** For every `flattened_to_string`, locate the actual rendering function in `prompt_assembly.py` (e.g. `render_capsule_prompt`, the `borrow ...; avoid ...` join at line 670). Capture file:line and the resulting string template.

4. **Trace each field forward to scorer.** Read `brand_gen/scoring/program.py` `BrandScorer.forward` and `signatures.py` `DescribeImage` / `AxisScore`. The input shape is small. For each plan field, mark whether it appears in the scorer signature directly, or only via the rendered prose `brand_dna` / `story_objective`.

5. **Trace each field to iteration memory.** Read `brand_gen/iteration_memory.py` `capture_feedback_into_iteration_memory` and the entry shape persisted to `iteration-memory.json`. Mark whether the field survives by ID/structure or is gone.

6. **Trace to disagreement records.** Per `docs/architecture/gepa-dspy-optimization.md`, disagreement-record fields include `axis_rationales`, `before_after_diffs`, `why_user_might_dislike_if_polished`. For each plan field, mark whether the disagreement record can address it.

7. **Build the matrix.** Output one row per plan field, four columns (scratchpad, scorer, iteration_memory, disagreement_record). Use four cell states: `preserved_struct`, `preserved_string`, `flattened`, `dropped`. Sum each column. Highlight rows where `flattened` or `dropped` appears in any of scorer/memory/disagreement — these are the lossy critical paths.

8. **Recommend the minimum surface extension.** Identify the smallest set of plan-field IDs (not full content) that, if added to scorer + iteration_memory + disagreement_record, would close the loop. Prefer adding ID/key references over duplicating full content.

## Reference files

- `brand_gen/pipeline_types.py:72` — `MaterialPlan` declaration.
- `brand_gen/plan_builder.py` — `create_material_plan` (the dict that exceeds the typed declaration).
- `brand_gen/generation_flow.py:329` — `assemble_generation_scratchpad`.
- `brand_gen/prompt_assembly.py:670` — example of structure-to-string flattening.
- `brand_gen/scoring/program.py`, `signatures.py` — the scorer input surface.
- `brand_gen/iteration_memory.py` — the persistence shape.
- `docs/architecture/gepa-dspy-optimization.md` — disagreement-record schema.

## Don't

- Don't propose adding the full plan dict to the scorer — that defeats the rubric. Recommend ID references.
- Don't conflate "string contains the information" with "system can reason about it". A `style_anchor: "moody minimal"` string carries the label but no machinery can address its archetype/capsule/mechanic constituents.
- Don't run this skill before `brand-gen-experiment-modeling` if `experiment_id` is on the recommendation list — the abstraction needs to exist before you can reference it.
