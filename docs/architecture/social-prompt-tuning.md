# Social prompt tuning pass — Sage v123

Target: `.brand-gen/brands/sage/scratchpads/generation/social-reference-generation-cb04ea438b5e.json`.
User score: 2.2/5.

## Iteration 0 alignment check

The social prompt asked for a community asset and a broader Sage capability
family, but the scratchpad did not require a source-knowledge lookup before
planning. The result could satisfy the words while still feeling generic.

## Fixed requirements

1. [critical] A Sage social prompt must cite one concrete Sage product/proof
   frame from brand memory or `brand_source_knowledge`.
2. [critical] Exact visible text must use deterministic rendering, or the native
   image prompt must be textless.
3. Inspiration must be translated as visual mechanics only; selected inspiration
   records and selected inspiration IDs must agree.
4. The prompt must ban generic capability diagrams unless every visible node maps
   to sourced Sage truth.
5. The prompt should keep proof subordinate to the brand field when the brief
   asks for a social promo.

## Findings

- The v123 scratchpad's prompt review already warned that exact text needed a
  deterministic strategy and that a proof-sensitive social lacked a selected
  `product_truth` role.
- Source knowledge was configured but unavailable as a typed read tool, so Pi
  agents had no reliable typed-tool-only way to inspect the Sage vault.
- Top-level `selected_inspiration_ids` included all configured inspiration
  source objects while `prompt_context.selected_inspiration_ids` named only the
  selected shortlist. That made inspiration lineage look broader/staler than the
  actual prompt block.

## Minimal edits applied

- Added `brand_source_knowledge` as a read-only typed tool so Pi agents can query
  brand-scoped Obsidian/docs excerpts before social planning.
- Updated the Pi Sage full-pipeline prompt to require `brand_source_knowledge`
  before Sage social planning.
- Recorded a durable Sage scratchpad note and forbidden pattern for generic
  capability diagrams without sourced Sage truth.
- Patched generation scratchpad assembly to persist only selected inspiration
  source records, keeping the board IDs and selected inspiration prompt block in
  sync.

Empirical executor dispatch note: a full clean-subagent empirical run was not
performed in this Codex turn because current tool policy only permits spawning
subagents when explicitly requested. This pass applies Iteration 0 plus the
runtime fixes surfaced by the v123 scratchpad evidence.
