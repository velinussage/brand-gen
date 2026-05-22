# Pi prompt: Sage brand-gen full pipeline with GEPA/DSPy feedback

Paste this into Pi from the brand-gen repository root when you want Pi to run the full brand material pipeline for the **Sage** brand.

```text
You are running brand-gen for the Sage brand from the brand-gen repository root.

Use the Pi brand-gen typed-tool runtime only. Do not run shell commands and do not edit JSON/markdown memory files directly. Prefer `/run orchestrator` and the `.pi/agents/*.md` contracts. If you need details, read these repo-local docs first:
- docs/architecture/runtime-agent-contract.md
- docs/architecture/gepa-dspy-optimization.md
- docs/architecture/aesthetic-curation.md
- docs/architecture/tool-groups/orchestration.md
- docs/architecture/tool-groups/mutation.md
- docs/architecture/tool-groups/inspection-policy.md

Goal: create or iterate a Sage brand material with the complete quality-gated pipeline and GEPA/DSPy-ready feedback capture.

Use this sequence:
0. Schema discipline: the tool names below are canonical. Use the actual Pi/MCP schema for each call and pass only schema-supported arguments. Do not invent typed-tool fields. Put extra creative detail into the tool's accepted free-text fields (`task`, `brief`, `prompt`, `user_request`, or equivalent) or into the `/run orchestrator` instruction.
1. Preflight: call typed inspection tools (`brand_context_snapshot`, `brand_source_knowledge`, `brand_list_brands`, `brand_capabilities`, `brand_show_blackboard`, `brand_show_iteration_memory`, `brand_scoring_status`). Confirm the active brand/session is Sage; if not, use `brand_switch_brand` for `sage`. Inspect `brand_context_snapshot.source_knowledge`; for Sage, if configured paths exist, query `brand_source_knowledge` for relevant vault details before planning and turn concrete product truth into prompt seeds or scratchpad notes. Do not assume Sage vault paths apply to other brands. If ambiguity remains, ask one concise question before generating. Ambiguity includes: Sage brand cannot be confirmed, material type/surface is unspecified, exact visible copy is requested without deterministic rendering, or a requested iteration has no clear `source_version`.
2. Pipeline: run `/run orchestrator "Create/iterate the requested Sage brand material using the full prepare → plan → validate → execute → review → evolve pipeline. Use typed brand_* tools only. Prefer orchestration tools over legacy CLI. Stop on blocking findings or needs_user_input."`
3. Planning: use `brand_orchestrate_material` for the normal path, or `brand_prepare_run`, `brand_plan_run`, and `brand_validate_run` for stage-level fall-through. If the user names a platform/surface, map it to the closest supported material type (for example X/social → x/social card). If the user names a look/style, pass it as `style_handle`; if a curated direction is known, pass `aesthetic_capsule`. Do not ask the image model to copy a protected studio/artist — brand-gen compiles shorthand into safe aesthetic descriptors. If no surface or material type is implied, ask one concise question rather than inventing one. For exact visible copy, require deterministic text rendering (HTML/SVG/composite/text overlay strategy), but for Sage do **not** route `social`, `editorial-card`, or content-card variants to `render_backend:"html"` just for labels; those HTML variants collapse into the same prompt-detail share-card. Use `proof-poster` as the single deterministic proof-card surface, or keep exact copy outside native image media. Do not spend generation tokens on plans that fail exact-text, brand-fit, reference-readiness, or WCAG gates.
4. Generation: use `brand_build_generation_scratchpad` / `brand_execute_run` with explicit real cinematographer fields when the schema supports them: `generation_mode`, `aspect_ratio`, `resolution`, `duration`, `source_version`, `reference_assets`, `motion_reference`, `base_image`, and `negative_prompt`. If the schema uses different names, preserve the intent using the supported fields. Do not bypass blocking findings (`allow_blocking`) unless the user explicitly authorizes a bypass; if a typed tool cannot express the needed bypass, stop rather than using shell.
5. Review: use the v2/DSPy scorer path when available (`brand_review_run` or `brand_critique_rubric`, whichever returns `rubric_version`). Always pass the required version argument (`version_id`/`version`) from the previous tool's `next_action`. Apply this decision rule exactly: `disqualifier_triggered == true` rejects; otherwise `overall_score < 3` iterates; otherwise approve. If review returns `decision: pending` or empty `axis_scores`, the artifact is not reviewed.
6. GEPA/DSPy trace quality: when user feedback or review disagreement is captured, preserve these reflection-ready fields in the disagreement record: `axis_scores`, `axis_rationales`, `disqualifier_triggered`, `disqualifier_rule`, `why_user_might_dislike_if_polished`, and `before_after_diffs`.
7. Iteration: convert each useful `before_after_diffs` row into typed mutations, not file edits. Use `brand_append_forbidden_pattern` for recurring `before` failures and `brand_append_custom_scratchpad_note` for `after` directives. Then re-run from the prior `source_version`.
8. Evolve: call `brand_evolve_run` only after an approved review or a submitted meaningful rejection. Do not evolve from a pending review packet, because that promotes stale or unrelated learnings and produces no disagreement record.
9. Final response: report the chosen version id, artifact paths, score/decision, disqualifier status, top axis scores, and the exact before/after diffs or durable mutations applied. If not approved, report the next action and the smallest typed-tool change needed.
```

## Notes for Sage-specific use

- Sage visuals should preserve the product truth: agents gaining trusted reusable capabilities from governed skill/prompt libraries, MCP tools, library manifests, and curated capability artifacts.
- For social prompts, query `brand_source_knowledge` first and pick one concrete Sage capability proof frame: skill library, prompt library, MCP tool card, agent workflow, library manifest, reusable capability tile, RLM feedback loop, or an agent receiving/installing a capability. Governance/review/promotion may appear as trust substrate only unless the task explicitly asks for governance education.
- Do not use invented Sage taxonomy such as `Prompt Pack`, `System of Provenance`, or `Approved Library Update`.
- If exact visible copy is needed, choose deterministic rendering; if using native image generation, make it a textless background/proof composition and add copy outside the image model.
- Deterministic HTML is currently useful for Sage only as `proof-poster`; do not create separate HTML `social` / `editorial-card` siblings for the same idea.
- Avoid generic AI slop: floating orbs, decorative robot brains, fake dashboards, unreadable pseudo-text, and abstract protocol diagrams with no artifact proof.
- Avoid generic capability-family diagrams unless each node maps to sourced Sage truth from the vault or brand memory.
- If visible copy is required, use approved Sage messaging or deterministic rendering. Do not ask an image model to invent readable text.
- Use `style_handle` for requested looks (for example, storybook warmth, screenprinted poster, civic documentary) and let the planner resolve a safe aesthetic capsule. Avoid default DAO/governance-theater imagery unless the source knowledge explicitly calls for it.
