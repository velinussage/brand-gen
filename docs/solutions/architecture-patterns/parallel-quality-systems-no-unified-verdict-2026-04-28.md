---
title: "P1/P2/P3, VLM, rubric axis_scores, and blackboard learnings never reconcile to a single Verdict"
date: 2026-04-28
track: knowledge
category: architecture-patterns
problem_type: unreconciled-verdict-systems
module: "brand_gen/scoring, brand_gen/blackboard.py, VLM critique flow"
status: resolved
severity: high
resolved: 2026-04-28
resolution_plan: docs/plans/2026-04-28-001-feat-brand-gen-pipeline-improvements-plan.md
resolution_units: [U5, U6]
related_files:
  - brand_gen/scoring/program.py
  - brand_gen/scoring/rubric_registry.py
  - brand_gen/scoring/signatures.py
  - brand_gen/blackboard.py
  - brand_gen/generation_flow.py
tags:
  - "scoring-architecture"
  - "verdict-reconciliation"
  - "vlm-critique"
  - "blackboard"
  - "quality-systems"
---

## Context

Brand-gen has **four independent quality assessment systems** that evolved at different times for different reasons and never reconcile their judgments:

1. **Structural critic (P1/P2/P3)** — text/structural review captured by `auto_capture_generation_feedback()` in `brand_gen/generation_flow.py` (~lines 1077-1114). P1=blocking, P2=should-fix, P3=nice-to-have. Maps: P1 → score 1 (negative), P2 → score 2 (negative), P3 → material note only.

2. **VLM critique** — visual review of the rendered image, captured by `auto_capture_vlm_feedback()` (~lines 1117-1164). Returns its own `p1`, `p2`, `approved`, `text_accuracy`, `palette_match`, `hallucinated_elements`. Approved → score 4 (positive).

3. **Scoring rubric (BrandScorer)** — DSPy-based axis scoring in `brand_gen/scoring/program.py` and `rubric_registry.py`. Universal axes (`composition`, `brand_coherence`, `restraint`, `story_fidelity`, `value_proposition_fidelity`) plus per-material overlays. Returns `axis_scores` (1-5 int), `decision` (approve/iterate/reject), `disqualifier_triggered`. Rubric version `2026-04-26`.

4. **Blackboard learnings** — long-running learning summary in `brand_gen/blackboard.py`, with `learning_summary`, `feedback_rollups`, `material_recipes`, and `decisions[]`. Aggregates via `update_blackboard_active_brief()` (~line 767).

The four systems agree about brand-gen quality ~80% of the time and disagree the other ~20%. There is **no shared decision arbiter** as of Apr 28. (session history)

## Guidance — canonical decision authority by gate

Until a unified `Verdict` type is introduced, treat each system as authoritative for one specific gate:

- **Pre-generation guardrails** → critic (P1/P2/P3).
- **Post-render visual gate** → VLM (`approved` flag, `hallucinated_elements`).
- **Numeric quality benchmark** → scoring rubric (`axis_scores`, `decision`, `disqualifier_triggered`). The `value_proposition_fidelity` axis is the user-calibrated guard for polished-but-wrong outputs; a score of 1 is treated as a hard iterate/reject signal through min-biased aggregation (`program.py:30-34`).
- **Cross-version learning** → blackboard.

## Why this matters

The four systems write into the **same** iteration memory (`capture_feedback_into_iteration_memory`, `add_iteration_note`) but with different score conventions:

- Critic P1 → score 1, P2 → score 2, P3 → notes only.
- VLM P1 → score 1, P2 → score 2, approved → score 4.
- Rubric `decision: reject` → has its own packet, does not flow into iteration memory automatically.
- Blackboard `learning_summary` → never scored; updated by stage progression.

Agents (and human operators) reading `iteration-memory.json` see a flattened mix of structural and visual scores **with no provenance**. A "score: 1" might be a P1 critic finding (text issue) or a VLM P1 (visual hallucination) or both — and the rubric may have approved it. This makes iteration decisions noisy and creates cases where the pipeline iterates on a structurally-fine-but-visually-broken output (or vice versa).

A real example: v148–v150 had `score: null` and `Status: blocked` in auto QA while agent reviews were still pending and a separate user score of 3.8/5 was clamped to 4 with a "user score 3.8/5" note. **Score precision was lost in the channel itself.** (session history)

## When to apply

- When debugging a "why did we re-iterate this version" question, check **all four** systems' verdicts; do not trust the iteration-memory score alone.
- When adding a new quality signal, decide explicitly which system owns it; do not invent a fifth.
- When scores disagree, prefer the rubric for numeric benchmarks (versioned, explicit axis definitions), the VLM for visual claims, and the critic for structural claims.
- Tag iteration-memory notes with provenance (`"Auto-critic: ..."` vs `"VLM critique: ..."` vs `"VLM approved: ..."` — already done in `generation_flow.py:1100, 1151, 1158`). Preserve that tag when reading.

## Examples

```python
# generation_flow.py:1097
score = 1 if p1 else 2          # critic
# generation_flow.py:1148
score = 1 if vlm_p1 else 2      # VLM
# generation_flow.py:1159
score = 4                       # VLM approved
# rubric — does not write `score`; writes `axis_scores: dict[str, int]` and `decision`
```

A version with conflicting verdicts in `iteration-memory.json`, `blackboard.json`, and the v2 critique packet is the canonical divergence signal. Reconcile by asking which gate the verdict was for.

## Open work

- The `brand-gen-verdict-unification` skill (`skills/brand-gen-verdict-unification/SKILL.md`) is a planning artifact, **not a code change**. Apr 28 audit named this as architectural risk #6.
- The "improvement-questions auto-resolution" rule (downgrade `quality_feedback` to `priority: 2 + auto_resolved: true` when iteration memory has negative examples) is a partial arbiter between iteration memory and quality questions only — not across all four systems.

## Pattern signal

```
auto_capture_generation_feedback / auto_capture_vlm_feedback   # two writers, same memory
capture_feedback_into_iteration_memory\(.*score=               # ambiguous score provenance
axis_scores: dict\[str, int\]                                  # rubric, not in iteration memory
"learning_summary"|"feedback_rollups"|"material_recipes"      # blackboard, separate file
P1/P2/P3 vs vlm_p1/vlm_p2 vs disqualifier_triggered vs decision  # four parallel verdicts
```

If the same version has different verdicts across `iteration-memory.json`, `blackboard.json`, and the v2 critique packet, that's the divergence. Reconcile by asking which gate each verdict was for; if no gate is identifiable, treat the rubric as authoritative.
