---
name: brand-gen-phase-contract-audit
description: >
  Audit the contract between pipeline phases (route → plan → validate → execute →
  review → evolve). Enumerate every Namespace field actually consumed via
  `getattr(args, ...)` per phase, compare against the typed PipelineRequest /
  MaterialPlan / GenerationScratchpad field sets, and identify "phantom" fields —
  ones referenced via getattr that have no schema declaration. Output a typed-vs-
  untyped contract gap matrix per phase, ranked by blast radius.
  USE WHEN: adding a new pipeline parameter, suspecting a phase is silently
  dropping fields, before refactoring pipeline_runner.py / pipeline_request.py,
  diagnosing tests that pass but production behavior drifts, or assessing whether
  the typed-runtime promise holds end-to-end.
  DO NOT USE WHEN: actually changing a phase signature (use ce-plan after this audit),
  or auditing prompt content (use brand-gen-truncation-audit).
compatibility:
  tools: [Bash, Read, Grep, Glob]
---

For Sage brand work in Pi, use the paste-ready prompt at `docs/prompts/pi-sage-brand-gen-full-pipeline.md`. Keep this link instead of copying the full prompt into skill bodies.

# Brand-Gen Phase Contract Audit

**Risk addressed:** the in-process contract between pipeline phases is `argparse.Namespace`. There are **426 `getattr(args, ...)` call sites across 16 modules**. `PipelineRequest.build_scratchpad_namespace` (`pipeline_request.py:332`) hand-builds a Namespace with ~30 fields just to pass typed data between in-process stages. `getattr(args, "field", None)` swallows typos, so renames silently zero out values. New fields require parallel updates in `PIPELINE_MCP_PROPERTIES`, `PipelineRequest`, `from_mapping`, `build_scratchpad_namespace`, the CLI builder, and per-phase `getattr` calls. Tests pass `argparse.Namespace()` so phantom fields slip through.

`PlanDraft` and `GenerationScratchpad` dataclasses *exist* but `_run_scratchpad` operates on the dict `payload` and converts at the end via `scratchpad_from_dict`. The `_filter_fields` helper (`pipeline_types.py:386`) silently drops unknown keys.

## What this skill produces

```json
{
  "summary": {
    "total_getattr_sites": 426,
    "phantom_fields": 17,
    "phases_with_drift": 4,
    "fields_declared_but_unused": 8,
    "namespace_fields_total": 73,
    "typed_request_fields_total": 41
  },
  "phases": [
    {
      "phase": "route",
      "consumed_fields": ["route_brief", "material_type", "render_backend", ...],
      "declared_in": ["PipelineRequest"],
      "phantom_in_phase": [],
      "untyped_via_namespace_only": ["route_force"]
    },
    {
      "phase": "plan",
      "consumed_fields": [...],
      "declared_in": ["MaterialPlan", "PipelineRequest"],
      "phantom_in_phase": ["legacy_inspiration_seed"],
      "untyped_via_namespace_only": ["accept_inspiration_recommendations"]
    }
    /* ... per-phase ... */
  ],
  "phantom_fields_detail": [
    {
      "field": "legacy_inspiration_seed",
      "read_at": ["plan_builder.py:412"],
      "never_written_at": "no PipelineRequest entry, no Namespace builder line",
      "default_returned": "None",
      "blast_radius": "silent — production has never set this; renames break nothing but the field is dead"
    }
  ],
  "filter_fields_drift": [
    {
      "field": "branch_id",
      "declared_in": "MaterialPlan, GenerationScratchpad",
      "missing_from": "scratchpad_from_dict input shape",
      "behavior": "silently dropped at deserialization"
    }
  ],
  "duplicate_field_routing": [
    {
      "field": "design_variance",
      "paths": ["PipelineRequest.design_variance", "Namespace.design_variance", "scratchpad payload.design_variance"],
      "consistency": "ok"
    }
  ]
}
```

## When to use

- Before adding a parameter to `bgen orchestrate-material` — to know how many sites need a parallel update.
- When a CLI flag works, an MCP call works, but the in-Python Namespace path silently no-ops.
- When `_filter_fields` drops a field you expected to survive.
- Before any refactor of `pipeline_runner._scratchpad_args` (`pipeline_runner.py:806`).
- To validate the typed-runtime promise that 45 MCP verbs hold end-to-end.

## Inputs

- Repo path (default `$PWD`).
- Optional `--phase <name>` — restrict audit to one phase. Otherwise audits all six.

## Procedure

1. **Build the typed-field universe.** Read `brand_gen/pipeline_types.py` and `brand_gen/pipeline_request.py`. Capture every dataclass field name from `PipelineRequest`, `RoutingBrief`, `PlanDraft`, `MaterialPlan`, `GenerationScratchpad`, `PipelineResult`, plus any nested types. Build a set keyed by `(class, field_name)`.

2. **Build the Namespace-field universe.** Read `PipelineRequest.build_scratchpad_namespace` (`pipeline_request.py:332`) and `pipeline_runner._scratchpad_args` (`pipeline_runner.py:806`). Capture every attribute set on `argparse.Namespace`. These are "fields the pipeline says exist."

3. **Build the consumed-field universe.** Grep `brand_gen/` for `getattr(args, "([^"]+)"`. Group results by enclosing function/file. Tag each function with its phase using these mappings:
   - `_run_route` / `route_brief` / `classify_workflow_route_smart` → route
   - `create_material_plan` / `_run_plan` / plan_builder.py functions → plan
   - `validate_*` / `_run_critique` → validate
   - `assemble_generation_scratchpad` / `execute_generation_scratchpad` / `_run_scratchpad` / `_run_generate` → execute
   - `apply_generation_critique_policy` / `vlm_critique` / `auto_capture_*` → review
   - `evolve_*` / `promote_*` → evolve

4. **Cross-reference to find phantoms.** For each `getattr(args, X)`, check whether `X` is in the typed-field universe AND in the Namespace-field universe. A phantom is a field consumed via getattr but absent from BOTH writers and ALL declared dataclasses. Mark these with their default-fallback so the user knows whether the silent-zero behavior matters.

5. **Find dead declarations.** For each typed dataclass field, check whether any `getattr(args, field)` references it. Fields declared but never read are dead.

6. **Audit `_filter_fields` drift.** Read `pipeline_types.py:386` (`_filter_fields`) and every caller of `from_dict` (`scratchpad_from_dict`, `plan_from_dict`, etc.). For each typed dataclass, check whether the `from_dict` reconciliation walks the same field set as the dataclass declares. Catch nested-key fallbacks (`pipeline_types.py:445-451`).

7. **Detect duplicate routing.** Some fields traverse multiple paths (CLI arg → Namespace → request → scratchpad payload). For each, walk the chain and verify name consistency.

8. **Rank blast radius.** Phantom fields rank highest if read in the execute phase (live prompt content). Drift in `_filter_fields` ranks high for any persisted field. Dead declarations are low-priority.

## Output schema

See "What this skill produces" above. Also emit a per-phase markdown table for human review:

```
| Phase | Consumed | Typed | Phantom | Drift |
|-------|----------|-------|---------|-------|
| plan  | 47       | 41    | 3       | 1     |
```

## Reference files

- `brand_gen/pipeline_request.py:332` — `build_scratchpad_namespace` (the Namespace contract).
- `brand_gen/pipeline_runner.py:806` — `_scratchpad_args` (the second Namespace builder).
- `brand_gen/pipeline_types.py:386, 445-451` — `_filter_fields` and nested fallback reconciliation.
- `brand_gen/cli_builders.py` — CLI args that flow into the Namespace.
- `brand_gen/commands/generation.py` — wires CLI to the runner.
- Project memory note: "New PipelineRunner params need 3 updates in `brand_iterate_mcp.py`: schema, Namespace, constructor." — verify the audit catches drift across these three sites.

## Don't

- Don't fix anything. Output the matrix; let `compound-engineering:ce-plan` design the migration to typed phase IO.
- Don't grep blindly: `getattr(obj, ...)` is used elsewhere in the codebase. Filter to `getattr(args, ...)` and to functions tagged with a pipeline phase.
- Don't include test files in the consumed-field universe — tests pass throwaway Namespaces and would inflate the phantom count.
