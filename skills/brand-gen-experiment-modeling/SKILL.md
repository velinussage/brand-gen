---
name: brand-gen-experiment-modeling
description: >
  Detect whether brand-gen has a first-class abstraction for aesthetic experimentation.
  Traces aesthetic_direction_brief.variants from creation in aesthetic_curation.py through
  plan_builder, prompt_assembly, scratchpad, and pipeline_runner. Reports whether
  `branch_id` / `parent_branch_id` (already declared in pipeline_types.py) are ever
  populated to anything other than workflow_id, whether scoring or critique can address
  individual variants, and whether the three parallel selection systems (archetype,
  capsule, design_variance) share any common Variant type. Recommends the shape of an
  AestheticExperiment dataclass and the seam where it should sit.
  USE WHEN: planning to A/B test aesthetic directions, building GEPA/DSPy candidate
  evaluation, debugging "why does iteration converge to one look", or before designing
  a Variant/Branch/Experiment abstraction.
  DO NOT USE WHEN: running a single generation pass (use brand-gen-orchestration), or
  investigating prompt size (use brand-gen-truncation-audit).
compatibility:
  tools: [Bash, Read, Grep, Glob]
---

# Brand-Gen Experiment Modeling

**Risk addressed:** brand-gen computes 2-3 ranked aesthetic variants in `build_aesthetic_direction_brief` (`brand_gen/aesthetic_curation.py:231`) — *and discards them*. Only the `_resolved_capsule` (one variant) flows into the prompt. `branch_id` and `parent_branch_id` exist in `pipeline_types.py:261` but are populated to `workflow_id` everywhere; nothing forks. Three parallel selection systems (`aesthetic_archetypes` rotation, `aesthetic_curation` capsule scoring, `surface_strategy` strategy scoring, plus a `design_variance` 1-10 dial) merge in `plan_builder.py:506-528` with no shared "Variant" type.

This skill answers: **does the system support trying N aesthetic directions and converging on one, today? If not, what's the smallest abstraction that would?**

## What this skill produces

```json
{
  "summary": {
    "first_class_variant_type_exists": false,
    "variants_materialized_per_run": 3,
    "variants_used_per_run": 1,
    "branch_id_populated_distinct_from_workflow": false,
    "parallel_selection_systems": 4,
    "shared_selection_signature": null
  },
  "variant_lifecycle": [
    { "stage": "create", "site": "aesthetic_curation.py:231 build_aesthetic_direction_brief", "shape": "{primary, alternates[2], difference_axes[], selection_rule}" },
    { "stage": "plan_attach", "site": "plan_builder.py:523", "shape": "embedded as plan['aesthetic_direction_brief'] dict" },
    { "stage": "prompt_consume", "site": "prompt_assembly.py:??", "shape": "prose render of primary only — alternates not referenced" },
    { "stage": "scratchpad_persist", "site": "generation_flow.py:assemble_generation_scratchpad", "shape": "?" },
    { "stage": "score_address", "site": "scoring/program.py BrandScorer", "shape": "no variant addressing — single brand_dna string" },
    { "stage": "iteration_memory_address", "site": "iteration_memory.py", "shape": "no variant addressing — flat per-version entries" }
  ],
  "selection_systems": [
    { "name": "aesthetic_archetype", "module": "aesthetic_archetypes.py", "score_fn": "pick_rotating_archetype", "output_type": "dict", "merges_at": "plan_builder.py:506-528" },
    { "name": "aesthetic_capsule", "module": "aesthetic_curation.py", "score_fn": "_capsule_score", "output_type": "dict", "merges_at": "plan_builder.py:506-528" },
    { "name": "surface_strategy", "module": "surface_strategy.py", "score_fn": "_score_strategy", "output_type": "dict", "merges_at": "plan_builder.py:506-528" },
    { "name": "design_variance_dial", "module": "card_engine.py", "score_fn": "n/a (int 1-10 from caller)", "output_type": "int", "merges_at": "card_engine.py taste_design_directives" }
  ],
  "branch_field_usage": [
    { "site": "pipeline_types.py:261 declaration", "populated_to": "n/a" },
    { "site": "pipeline_runner.py", "populated_to": "workflow_id (no actual branching)" }
  ],
  "recommendation": {
    "abstraction": "AestheticExperiment",
    "fields": ["experiment_id", "parent_experiment_id", "variants: List[Variant]", "selected_variant_id", "selection_rationale", "scoring_dimension", "decision_state"],
    "variant_fields": ["variant_id", "archetype", "capsule", "surface_strategy", "design_variance", "selection_score", "selection_reasons", "differentiating_axes"],
    "seam": "between MaterialPlan (plan-build phase output) and GenerationScratchpad (execute phase input)",
    "minimum_changes": ["promote variants[] from plan dict to typed list", "carry through generation_flow scratchpad payload", "extend BrandScorer.forward to accept variant context", "extend iteration_memory entries to reference variant_id"]
  }
}
```

## When to use

- Before any GEPA/DSPy work — variant identity is a prerequisite for paired comparison.
- When the user asks "did we ever try direction X?" and you have no structured answer.
- When `bgen suggest-aesthetic-directions` produces 3 variants but the next pipeline run uses only one without recording why.
- When iteration converges to a local maximum and you want explicit branch tracking.

## Inputs

- Repo path (default `$PWD`).
- Optional `--include-ui` — also check `brand-orchestrator` agent surface for whether variant addressing is exposed.

## Procedure

1. **Find the variant creation point.** Read `brand_gen/aesthetic_curation.py:231-265` (`build_aesthetic_direction_brief`). Note the variant dict shape: `primary`, `alternates`, `difference_axes`, `selection_score`, `selection_reasons`, `selection_rule`.

2. **Trace forward.** From `aesthetic_curation.build_aesthetic_direction_brief`, find every site that consumes its output. Grep for `aesthetic_direction_brief`, `direction_brief`, `alternates`, `variants`. Record for each: which fields it reads, whether it consumes `primary` only or all variants, whether the alternates are persisted or dropped.

3. **Trace the parallel selection systems.** For each of `aesthetic_archetypes.pick_rotating_archetype`, `aesthetic_curation.select_aesthetic_capsule`, `surface_strategy.recommend_surface_strategies`, capture: function signature, return shape, score function (if any), where it's called in `plan_builder.py`, whether the unselected candidates are persisted.

4. **Audit `branch_id` / `parent_branch_id` usage.** Grep all of `brand_gen/` for these field names. For each write site, capture what value gets assigned (look for `workflow_id`, literal strings, derivations). For each read site, capture what the consumer does with it.

5. **Audit downstream variant addressability.**
   - **Scoring**: read `brand_gen/scoring/program.py`, `signatures.py`, `rubric_registry.py`. Does any input field accept a variant identifier? Are scores aggregated per-variant or per-version-only?
   - **Iteration memory**: read `brand_gen/iteration_memory.py`. Are entries keyed by variant or only by version?
   - **Disagreement records**: per `docs/architecture/gepa-dspy-optimization.md`, do `axis_rationales` / `before_after_diffs` carry variant context?

6. **Detect the shared signature gap.** Compare the four selection systems. Do they share a `(score: float, reasons: List[str])` shape? Is there a candidate base class? Is `Selection` / `Candidate` declared anywhere typed?

7. **Recommend the minimum abstraction.** Based on findings, output an `AestheticExperiment` recommendation:
   - Where it should sit in `pipeline_types.py`.
   - What `MaterialPlan` fields become `experiment_id` references.
   - What changes in `assemble_generation_scratchpad` to carry variant context.
   - What scorer signature change addresses variants.
   - The minimum migration path (which existing fields stay, which are wrapped).

## Reference files

- `brand_gen/aesthetic_curation.py:231-265` — the variant creation site (good seed shape).
- `brand_gen/aesthetic_archetypes.py:78-101` — rotating archetype, parallel selection system #1.
- `brand_gen/surface_strategy.py:192-279` — `_score_strategy`, parallel system #2.
- `brand_gen/plan_builder.py:506-528` — merge point where structure collapses.
- `brand_gen/pipeline_types.py:261` — `branch_id` / `parent_branch_id` declarations (currently unused).
- `brand_gen/scoring/program.py` — scorer surface that needs variant addressing.
- `docs/architecture/aesthetic-curation.md` — design intent vs. implementation.
- `docs/architecture/gepa-dspy-optimization.md` — disagreement-record fields that depend on variant identity.

## Don't

- Don't implement the abstraction inside this skill. Output the recommendation; let `compound-engineering:ce-plan` plan the migration.
- Don't conflate "the system tracks rotation" (it does, weakly) with "the system has experiments" (it doesn't).
- Don't recommend renaming `branch_id` — it's already there. Recommend populating it.
