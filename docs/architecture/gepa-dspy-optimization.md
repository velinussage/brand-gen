# GEPA and DSPy optimization plan for brand-gen

This is the architecture contract for using GEPA/DSPy to improve brand-gen's planner, critic, cinematographer, scratchpad, and host-agent prompts. It lives in the repo-local `docs/architecture/` folder so the optimization plan travels with brand-gen instead of depending on a personal agent cache.

## Source scan

Lakshya Agrawal's Apr 23, 2026 X thread frames GEPA as a reflective optimizer now embedded in DSPy and used for agent self-evolution, `optimize_anything`, safety monitors, information extraction, and production case studies. The relevant pattern for brand-gen is not “collect a scalar score and tune one prompt.” It is “record rich traces and textual evaluator feedback, then search over prompts / policies / agent contracts with Pareto selection.”

Primary sources:

- X thread: `https://x.com/LakshyAAAgrawal/status/2047399377174429946`
- GEPA project: `https://gepa-ai.github.io/gepa/`
- DSPy GEPA docs: `https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/GEPA/overview.md`
- optimize_anything blog: `https://gepa-ai.github.io/gepa/blog/2026/02/18/introducing-optimize-anything/`

## Pipeline implications

1. **Keep disagreement records reflection-rich.** Brand-gen disagreement records must preserve textual failure evidence, not only `agent_score`/`user_score`.
2. **Optimize multiple text artifacts.** Candidate artifacts should include planner instructions, critic rubric wording, cinematographer prompt rules, scratchpad assembly policy, tool schema descriptions, and `.pi`/Claude agent contracts.
3. **Use Pareto objectives.** Preserve candidates that specialize by material type or failure bucket instead of keeping only the highest global average.
4. **Use DSPy where the scorer is already a program.** The v2 critic/scorer path should expose a DSPy module whose metric returns score plus textual feedback.
5. **Use GEPA/optimize_anything for agent contracts.** Agent markdown, tool schemas, and validation snippets are text artifacts with measurable outcomes.

## Reflection-ready disagreement schema

When user feedback produces an agent-vs-user score pair, `brand_gen.commands.review._maybe_log_disagreement()` appends a JSONL record to the disagreement dataset. The record now carries these GEPA/DSPy-ready fields:

| Field | Purpose |
|---|---|
| `axis_scores` | Per-axis numeric critique signal for localized optimization. |
| `axis_rationales` | Per-axis textual reasoning for GEPA reflection. |
| `disqualifier_triggered` | Boolean hard-fail signal for recall/precision tracking. |
| `disqualifier_rule` | The rule ID or name that caused the hard fail. |
| `why_user_might_dislike_if_polished` | Human-centered critique for polished-but-wrong outputs. |
| `before_after_diffs` | Concrete rewrite rows: what failed before and what the next candidate should do after. |

These fields are intentionally compact. They should be enough for a reflection model to explain why a scorer/user disagreement happened without storing the full image prompt, full artifact, or personal machine context.

## Evaluation objectives

Track candidate prompt/policy changes with at least these objectives:

- **Agreement delta:** reduction in `abs(agent_score - user_score)` by material type.
- **Disqualifier recall:** how often hard failures are caught before generation is approved.
- **Disqualifier precision:** how often hard failures are true blockers rather than over-strict false positives.
- **Before/after usefulness:** fraction of `before_after_diffs` rows that translate into durable `append-forbidden-pattern` or scratchpad-note mutations.
- **Exact-text gate precision/recall:** whether exact-text requests are blocked only when deterministic rendering is missing.
- **Value proposition fidelity:** whether Sage materials show agents gaining trusted reusable capabilities, rather than proposal/governance process, invented taxonomy, generic trust imagery, or logo-as-content substitutes.
- **Cost/runtime:** total generation + review cost per accepted artifact.
- **User rejection rate:** post-polish user rejection rate, especially for “looks good but wrong” cases.

## First optimization targets

1. Exact-text gate phrases and negation windows.
2. Brand-planner prompt seed contract.
3. Brand-critic before/after diff quality.
4. Cinematographer seven-rule validation wording and scratchpad arguments.
5. Tool schema descriptions for high-error verbs.
6. Short `.pi` typed-tool-only agent bodies.

## User-calibrated Sage value failure

The current v2 rubric includes `value_proposition_fidelity` as a universal axis. For Sage work:

- **5** — clearly shows agents gaining trusted reusable capabilities from skill/prompt libraries, MCP tools, library manifests, or curated capability artifacts.
- **3** — hints at capabilities but uses vague trust/provenance imagery or fuzzy terms.
- **1** — focuses on proposal/governance/review/publish process instead of capability distribution, invents product taxonomy, or uses the logo as the content substitute.

GEPA/DSPy candidates should treat `value_proposition_fidelity=1` like a hard user-calibrated failure even if craft/composition axes look polished.

### v176-v179 Sage calibration rows

The local Sage disagreement dataset has a manual calibration batch for
`v176`-`v179` (`rubric_version:
2026-04-27-v176-v179-calibration`):

- Reward `v178` (`editorial-metaphor-illustration`, 4/5): crafted routing
  loom, Behavior into thin harness, and a visible adoption/use outcome.
- Penalize `v176`, `v177`, and `v179` (1/5): repeated Sage logos, generic
  adoption scenes that do not feel sourced, weak vault-language usage, and
  poster/card/default routes for capability explanation.

Future GEPA runs should preserve the `v178` direction while treating repeated
logos and missing Sage vault specificity as explicit disqualifier evidence.

## Implementation rule

Any future GEPA/DSPy run should write its candidate prompt/policy artifacts as files under this repository and evaluate them against disagreement records. Do not hide optimized contracts in local home-directory prompts where Pi/Claude/OpenClaw cannot resolve the same architecture.
