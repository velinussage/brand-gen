---
name: brand-gen-verdict-unification
description: >
  Catalog every emitter of a quality verdict in brand-gen — visual_review_status,
  axis_scores, vlm_approved, critique_policy decisions, render verification,
  generation_flow auto-critic. Map each to a single proposed Verdict schema.
  Flag every place where verdicts are silently combined into a single string field
  (e.g. visual_review_status). Recommend a unified Verdict dataclass and the
  composition rules that resolve conflicts.
  USE WHEN: planning to add a new quality gate, reconciling "the critic said pass
  but the policy said block", before adding a manifest field that overlaps an
  existing verdict, or unifying review/critique/critic naming.
  DO NOT USE WHEN: scoring a single image (use the existing scorer), or
  investigating how verdicts feed into iteration_memory (use
  brand-gen-intent-preservation-trace).
compatibility:
  tools: [Bash, Read, Grep, Glob]
---

# Brand-Gen Verdict Unification

**Risk addressed:** brand-gen has at least four parallel quality systems with non-fungible outputs, composed implicitly:

1. `card_engine._verify_render` — file-level checks (PNG magic, headline presence) → gates `visual_review_status` to `"render_suspect"`.
2. DSPy `BrandScorer` (`scoring/program.py`) — rubric-based axis scoring with `axis_scores`, `axis_rationales`, `decision: approved | iterate`.
3. `vlm_critique` — VLM gate with `approved | rejected` decision (legacy path).
4. `apply_generation_critique_policy` (`generation_flow.py`) — policy mode (advisory vs strict), can block.
5. `build_structural_auto_critic` (`generation_flow.py:1016`) — structural pre-flight critic.
6. `agent_review` packet — orchestrator-level review record.

Each writes a different shape onto manifest entries. Naming is overloaded: "review" vs "critique" vs "critic" vs "feedback" are not consistently distinguished. There is no place where a downstream consumer can ask "what's the unified verdict for this version?" — they have to read 4-6 fields and apply implicit precedence.

## What this skill produces

```json
{
  "summary": {
    "verdict_emitters_total": 6,
    "manifest_fields_carrying_verdicts": 9,
    "implicit_combination_sites": 3,
    "conflicting_verdict_paths": 2,
    "naming_synonyms": ["review", "critique", "critic", "feedback", "verdict", "decision"]
  },
  "emitters": [
    {
      "emitter": "card_engine._verify_render",
      "site": "card_engine.py:1500-1540 (approx)",
      "verdict_shape": "{visual_review_status: 'pending' | 'render_suspect'}",
      "scope": "file-level (per PNG)",
      "blocking": false,
      "writes_to": ["manifest.entries[].visual_review_status"]
    },
    {
      "emitter": "BrandScorer.forward",
      "site": "scoring/program.py BrandScorer",
      "verdict_shape": "{axis_scores: {...}, axis_rationales: {...}, decision: 'approved' | 'iterate'}",
      "scope": "rubric-level (per version)",
      "blocking": false,
      "writes_to": ["review-packet.json", "manifest entry decision"]
    },
    {
      "emitter": "vlm_critique",
      "site": "vlm_critique.py",
      "verdict_shape": "{approved: bool, rationale: str}",
      "scope": "image-level (per version)",
      "blocking": false,
      "writes_to": ["iteration_memory positive/negative"]
    },
    {
      "emitter": "apply_generation_critique_policy",
      "site": "generation_flow.py apply_generation_critique_policy",
      "verdict_shape": "{policy_status: 'allow' | 'block', mode: 'advisory' | 'strict', findings: [...], bypassable: bool}",
      "scope": "policy-level (per run)",
      "blocking": true,
      "writes_to": ["pipeline_result.stop_reason", "run_ledger event"]
    },
    {
      "emitter": "build_structural_auto_critic",
      "site": "generation_flow.py:1016",
      "verdict_shape": "{P1: [...], P2: [...], P3: [...]}",
      "scope": "scratchpad-level (pre-execute)",
      "blocking": "indirect — drives iteration_memory negatives",
      "writes_to": ["iteration_memory negatives via auto_capture_generation_feedback"]
    },
    {
      "emitter": "agent_review",
      "site": "agent_review.py",
      "verdict_shape": "{orchestrator_review_packet: {...}}",
      "scope": "orchestration-level (per run)",
      "blocking": false,
      "writes_to": ["agent-review packet json"]
    }
  ],
  "implicit_combination_sites": [
    {
      "site": "manifest entry decision_field_resolution",
      "issue": "no documented rule for which verdict wins when render says render_suspect, scorer says approved, policy says allow"
    }
  ],
  "conflicting_verdict_paths": [
    {
      "scenario": "vlm_critique approved + apply_generation_critique_policy block",
      "current_behavior": "policy blocks the run; vlm verdict is recorded but does not gate",
      "documented": false
    }
  ],
  "recommended_verdict_schema": {
    "name": "Verdict",
    "fields": [
      "verdict_id",
      "version_id",
      "emitter: enum",
      "scope: enum",
      "decision: enum (approve | iterate | block | flag)",
      "blocking: bool",
      "rationale: str",
      "axis_scores: dict | null",
      "findings: list[Finding] | null",
      "supersedes: List[verdict_id]"
    ],
    "composition_rule": "blocking emitter (policy) > rubric (scorer) > image (vlm) > file (render verification) > pre-flight (auto-critic). Equal scope: most-recent supersedes older.",
    "manifest_field": "manifest.entries[].verdicts: List[Verdict]; manifest.entries[].resolved_verdict: Verdict (computed)"
  }
}
```

## When to use

- Before adding ANY new quality gate — verify it slots into the schema instead of adding a 7th parallel system.
- When the orchestrator's `stop_reason` doesn't match the user's perception of "did this pass."
- When `iteration_memory` learns from VLM but ignores policy findings (or vice versa).
- Before unifying agent-facing language across the brand-orchestrator / brand-critic / brand-explorer surface.

## Inputs

- Repo path (default `$PWD`).
- Optional `--include-naming` — also emit a synonym normalization table for "review/critique/critic/feedback".

## Procedure

1. **Enumerate verdict-bearing fields on the manifest.** Read `brand_gen/generation_flow.py` (manifest entry assembly) and `card_engine.py` (`_verify_render`). Find every field whose value is a quality decision string or struct: `visual_review_status`, `decision`, `policy_status`, `vlm_decision`, `agent_review_status`, etc.

2. **Locate every emitter.** For each manifest field, walk back to the function that computes it. Capture: emitter function file:line, output shape (what fields the emitter sets), what scope it covers (file / rubric / image / policy / scratchpad / orchestration), whether it is blocking (gates the run) or advisory.

3. **Detect implicit combination.** Search `pipeline_runner.py`, `generation_flow.py` for sites that read multiple verdict fields and produce a derived state (`stop_reason`, `next_action`, `decision`). Flag any site where the precedence is not explicit (no documented rule, no comment, no test).

4. **Find conflicting paths.** Pairwise check each emitter combination and look for cases where the system would emit divergent verdicts. Read tests under `tests/test_critique_policy.py`, `tests/test_generation_flow.py` to confirm whether documented behavior covers the conflict.

5. **Audit naming.** Grep for `review`, `critique`, `critic`, `feedback`, `verdict`, `decision`, `status`, `judgment`. Build a synonym map keyed by which module owns each term. Highlight cases where two terms refer to the same concept (e.g. `agent_review_status` vs `vlm_decision`).

6. **Recommend the unified schema.** Define a `Verdict` dataclass with explicit composition rules. Recommend the precedence order (typically: blocking-policy > rubric > image > render > pre-flight). Recommend the manifest extension (`verdicts: List[Verdict]` plus a computed `resolved_verdict`). Identify the minimum migration path that doesn't break existing tests.

## Reference files

- `brand_gen/card_engine.py` — `_verify_render`, the file-level emitter.
- `brand_gen/scoring/program.py`, `signatures.py`, `rubric_registry.py` — the rubric emitter.
- `brand_gen/vlm_critique.py` — the image emitter (legacy path).
- `brand_gen/generation_flow.py:1016` — `build_structural_auto_critic` (pre-flight emitter).
- `brand_gen/agent_review.py` — the orchestration packet.
- `brand_gen/critique_policy.py` — the policy emitter.
- `tests/test_critique_policy.py` — test surface that already constrains some combinations.

## Don't

- Don't replace existing emitters. Wrap their outputs in `Verdict` and let the resolved-verdict logic compose.
- Don't overreach into iteration_memory entry shape — that's `brand-gen-intent-preservation-trace`'s territory. Only state what the emitter writes there.
- Don't propose deleting `vlm_critique` even if it's deprecated — its output may still be the only image-level signal in legacy flows. Recommend deprecation path, don't shortcut it.
