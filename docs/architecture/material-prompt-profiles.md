# Material prompt profiles

`data/material_prompt_profiles.json` is the material-by-material prompt contract for brand-gen. It covers the five testing batches (proof/social, product/interface, brand system, editorial/content, and motion/video) and keeps material-specific guidance out of long agent prompts.

Each profile defines:

- `job_to_be_done` — what the material must accomplish.
- `generation_mode`, `default_aspect_ratio`, `default_model`, `default_render_backend` — runtime/default rendering expectations.
- `exact_text_policy` — whether exact copy requires deterministic HTML/SVG/composite/external overlay.
- `best_aesthetic_capsules` — the preferred curated aesthetic capsules for the material.
- `allowed_reference_roles` — role-pack roles that are valid for this material (`composition`, `motif`, `application`, `motion`, `product_truth`).
- `prompt_skeleton` — the minimal shape the prompt should preserve.
- `negative_prompt_failure_bans` — material-specific failure modes to block.
- `review_focus` — what reviewers/scorers should inspect first.
- `web_delivery` — optional deployability metadata for web media (file type, dimensions, loop duration, reduced-motion fallback).
- `review_rubric_key` / `review_rubric_mapping` — material-specific overlay when available, otherwise universal rubric axes.

`landing-hero` is intentionally a 16:9 hero background/sidecar animation profile now, not a full webpage still. It defaults to `seedance-2-pro`, primary MP4 output, 1600×900 display target, external page copy, and no native nav/headline/CTA. Use `website-hero-illustration` when the desired deliverable is static art beside hero text. `bumper-animation` is deprecated for default sets because generic logo stings were not carrying a clear product purpose; prefer `landing-hero`, `feature-animation`, or explicit `logo-animation`.

## Runtime use

Planning embeds the profile into every plan as `material_prompt_profile`. Scratchpad assembly passes it into prompt assembly, which injects a compact `material_profile_block` into the execution prompt. This makes every material type carry its own process/context rules even when the agent prompt is short.

Aesthetic capsule selection also consults `best_aesthetic_capsules`, so material variants without direct capsule `material_types` still select a sane family default.

## Product-truth contract for Sage materials

Sage-specific capability materials now get an additional high-priority `product_truth_contract` block before aesthetic guidance. The contract is intentionally narrow: it prevents the pipeline from turning governance machinery into the whole asset when the actual value story is agent capability distribution.

For Sage, default visuals should lead with agents discovering, receiving, installing, or reusing trusted capabilities from skill/prompt libraries. Use concrete artifacts such as skill cards, MCP tool cards, library manifests, curated capability tiles, agent runtime/install moments, and reusable workflow cards.

Governance/review/promotion may appear as a compact trust badge or substrate, but it should not become the visual hero unless the material explicitly asks for governance education or a proposal/governance snapshot. The validator blocks the `wrong_value_hero: proposal_process_instead_of_capability_distribution` failure before generation.

The same contract bans invented product taxonomy (`Prompt Pack`, `System of Provenance`, `Approved Library Update`), fake product modules/screens, generic trust-layer claims, and logo-as-content substitutes. For explanatory assets, the Sage mark should be a small provenance seal/corner/source marker, not the centerpiece.

For text-heavy materials (`data-card`, `process-card`, `badge-family`, `social`, `proof-poster`, and related cards), native image generation should be mostly textless; exact labels, stats, captions, badges, or card copy belong in deterministic HTML/SVG/composite overlays.

## Tests

`tests/test_material_prompt_profiles.py` enforces that every requested batch material has:

- runtime support in `MATERIAL_CONFIG`
- a prompt profile
- at least one valid aesthetic capsule or explicit fallback
- a clear exact-text policy
- a review rubric mapping

Run:

```bash
pytest tests/test_material_prompt_profiles.py -q
```

## Adding a material

1. Add or confirm the material in `data/material_policy.json` / `MATERIAL_CONFIG`.
2. Add it to the relevant `batches` list in `data/material_prompt_profiles.json`.
3. Add a profile with all required fields.
4. If the material needs a new style family, add an aesthetic capsule in `data/aesthetic_capsules.json`.
5. Run the profile tests and `tests/test_mcp_schema_parity.py` if the change affects host tools.
