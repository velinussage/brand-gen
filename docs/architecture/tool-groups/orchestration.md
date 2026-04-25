# Orchestration tools

Use these for run-stage movement. They are the only tools that should advance generation state.

- `brand_prepare_run` — inspect brand DNA, learnings, readiness.
- `brand_plan_run` — create a plan draft. Requires `material_type`; accepts `style_handle` and `aesthetic_capsule` for curated look selection.
- `brand_validate_run` — critique/gate a plan. Requires `plan_draft`.
- `brand_execute_run` — paid generation. Requires approved `plan_draft`.
- `brand_review_run` — score generated output. Requires `version_id`.
- `brand_evolve_run` — promote learnings and next questions.
- `brand_orchestrate_material` — convenience wrapper for the six-phase loop; accepts the same style fields as planning (`style_handle`, `aesthetic_capsule`).
- `brand_build_generation_scratchpad` — assemble execution scratchpad without paid generation; used by video/cinematographer and debugging.

`brand_build_generation_scratchpad` accepts video-ready fields: `prompt`, `generation_mode`, `aspect_ratio`, `duration`, `source_version`, `reference_assets`, `motion_reference`, `base_image`, and `negative_prompt`.


## Aesthetic style fields

When the user names a look, pass `style_handle` instead of trying to rewrite it from first principles. If the direction is ambiguous, run `bgen suggest-aesthetic-directions` (CLI/operator fallback) to compare 2-3 moodboard branches before planning. When the exact curated direction is known, pass `aesthetic_capsule`. The planner resolves these into an `aesthetic_capsule_block` in the scratchpad; see `../aesthetic-curation.md`.
