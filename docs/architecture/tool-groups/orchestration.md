# Orchestration tools

Use these for run-stage movement. They are the only tools that should advance generation state.

- `brand_prepare_run` — inspect brand DNA, learnings, readiness.
- `brand_plan_run` — create a plan draft. Requires `material_type`.
- `brand_validate_run` — critique/gate a plan. Requires `plan_draft`.
- `brand_execute_run` — paid generation. Requires approved `plan_draft`.
- `brand_review_run` — score generated output. Requires `version_id`.
- `brand_evolve_run` — promote learnings and next questions.
- `brand_orchestrate_material` — convenience wrapper for the six-phase loop.
- `brand_build_generation_scratchpad` — assemble execution scratchpad without paid generation; used by video/cinematographer and debugging.

`brand_build_generation_scratchpad` accepts video-ready fields: `prompt`, `generation_mode`, `aspect_ratio`, `duration`, `source_version`, `reference_assets`, `motion_reference`, `base_image`, and `negative_prompt`.
