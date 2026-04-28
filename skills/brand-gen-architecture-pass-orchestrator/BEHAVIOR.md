# brand-gen-architecture-pass — Orchestrator Behavior

**Purpose:** run a complete architectural assessment of `brand-gen` and produce a single ranked, actionable improvement plan. Composes the six audit skills in this library, merges their outputs, and hands a remediation plan to `compound-engineering:ce-plan` for implementation sequencing.

**Use when** the user says any of:
- "do an architecture pass on brand-gen"
- "assess brand-gen for architectural risk / fragility"
- "plan the next architecture improvement pass"
- "run the architecture audit"
- "diagnose brand-gen's iteration loop"

**Do not use when** the user wants to generate brand materials, run a single pipeline, change one file, or investigate one bug. This behavior is for systemic assessment, not point fixes.

## Required skills (hard dependencies)

Every run executes all six. They are independent — run them in parallel.

1. `brand-gen-truncation-audit` — manifest of every prompt cap site (risk #2).
2. `brand-gen-experiment-modeling` — variant lifecycle, parallel selection systems, AestheticExperiment recommendation (risk #1).
3. `brand-gen-phase-contract-audit` — phantom Namespace fields, typed-vs-untyped gap matrix (risk #4).
4. `brand-gen-intent-preservation-trace` — MaterialPlan field survival to scratchpad, scorer, iteration_memory (risk #3).
5. `brand-gen-verdict-unification` — verdict emitter catalog, unified Verdict schema recommendation (risk #6).
6. `brand-gen-loop-shape-assessment` — actual vs desired state machine, missing back-edges (risk #5).

## Optional skills

- `compound-engineering:ce-plan` — convert each ranked finding into a structured implementation plan.
- `compound-engineering:ce-doc-review` — get persona reviews of the merged punch-list document before planning.
- `pre-mortem` — run on the proposed remediation plan before any code changes.
- `compound-engineering:ce-compound` — record learnings after the pass completes.
- `empirical-prompt-tuning` — for any prompt-assembly fix derived from the truncation audit.

## Inputs

- `repo_path` — absolute path to the brand-gen working directory (default: `$PWD`).
- `output_path` — where to write the merged report (default: `<repo>/docs/architecture/architecture-pass-<YYYY-MM-DD>.md`).
- `skip` (optional list) — skill keys to skip if a prior partial run produced fresh output.
- `cap_findings` (optional int, default 12) — max findings carried into the planning step.

## Procedure

### Phase 1 — Run the six audits in parallel

For each of the six required skills, dispatch with `repo_path` as input. Do not run them sequentially; the audits are independent and the wall-clock matters when the user is waiting. Each skill returns a JSON-shaped result; capture the raw output without interpretation.

If any skill fails, do not abort the pass. Capture the failure and continue. The merged report should call out missing data explicitly so the user knows which dimensions weren't audited.

### Phase 2 — Cross-reference

Some findings reinforce each other. Build the cross-reference set BEFORE ranking:

- Every cap site flagged by `brand-gen-truncation-audit` that operates on a hard-constraint section AND that section's plan field is flagged "lost to scorer" by `brand-gen-intent-preservation-trace` is a **double-loss finding** — promote to top of ranking.
- Every selection system identified by `brand-gen-experiment-modeling` whose output is "flattened to string" in `brand-gen-intent-preservation-trace` is a **structure-drop finding** — these are the cheapest wins.
- Every phantom field from `brand-gen-phase-contract-audit` that lives in the execute or review phase is a **runtime-undefined finding** — escalate severity.
- Every verdict emitter from `brand-gen-verdict-unification` that gates `pipeline_result.stop_reason` AND has no documented composition rule is an **implicit-precedence finding** — gate before any new quality gate is added.
- Every missing back-edge from `brand-gen-loop-shape-assessment` whose target phase is on the dependency list of an `AestheticExperiment` (per `brand-gen-experiment-modeling`) is a **convergence-blocker finding** — must precede the variant abstraction work.

### Phase 3 — Rank findings

Rank by leverage, not severity. Use this scoring:

```
leverage = (consumers_affected × signal_loss) / migration_blast_radius
```

- `consumers_affected` — how many downstream stages read the affected field/site.
- `signal_loss` — 0 if tracked, 1 if silent (truncation, phantom field, lost variant, dropped verdict).
- `migration_blast_radius` — file count + test count that change to fix it. Approximate from each skill's "minimum_change" or "minimum_extension" field.

Cap to `cap_findings` (default 12). Below that, a remediation plan loses focus.

### Phase 4 — Write the merged report

Write to `output_path` a markdown document with this structure:

```markdown
# Brand-Gen Architecture Pass — <date>

## Executive summary
- Total findings: N (top <cap_findings> ranked below).
- Highest-severity dimension: <truncation | experiment | contract | intent | verdict | loop>.
- Cheapest wins (≤1 file, no test churn): N.
- Convergence blockers: N (must precede experiment work).
- Audit gaps: <skills that failed, if any>.

## Top findings (ranked)

For each finding:

### N. <name> — leverage: <score>
**Dimension:** <skill key>
**Evidence:** <one paragraph, with file:line references>
**Reinforced by:** <other skills that flagged adjacent issues>
**Minimum change:** <from the source skill's recommendation>
**Blast radius:** <files + tests touched>
**Block on:** <other findings that must land first, if any>

## Per-skill raw outputs

(Embed each skill's JSON output verbatim under a level-3 heading.)

## Recommended sequencing

A topological order respecting "Block on" edges. Group findings into 3 waves:
1. **Foundation** — abstractions that other findings depend on (typically the `AestheticExperiment`).
2. **Loss-stoppers** — silent truncation / phantom field / dropped verdict fixes.
3. **Loop-closers** — back-edges, candidate-set carrying, scorer extensions.
```

### Phase 5 — Hand off to planning

Invoke `compound-engineering:ce-plan` with the merged report as input. Ask it to produce a numbered, structured implementation plan with one task per finding. The orchestrator's job ends there — implementation is out of scope.

Optionally invoke `pre-mortem` on the resulting plan before any code changes. Especially for findings that touch `pipeline_runner.py`, `prompt_assembly.py`, or `pipeline_types.py` — the blast radius is high and a pre-mortem catches second-order failures.

### Phase 6 — Record the run

Append a one-line summary to the brand-gen run-ledger style log under `<repo>/docs/architecture/architecture-pass-log.md`:

```
- <date>: <total findings> findings, top dimension: <name>, blocker count: <n>, plan path: <ce-plan output>
```

This lets the next pass see what was assessed and whether the previous pass's findings were actually addressed.

## Output contract

The orchestrator must return:

```json
{
  "report_path": "...",
  "plan_path": "...",
  "findings_total": 17,
  "findings_ranked": 12,
  "convergence_blockers": 2,
  "audit_gaps": []
}
```

## Don'ts

- Don't run the audits sequentially. They're independent. Parallelism matters.
- Don't filter findings before merging. Cross-references reveal double-losses; filtering breaks that.
- Don't skip the cross-reference phase. The whole point of running six audits is the interaction effects.
- Don't propose fixes inside this behavior. Fixes belong to `ce-plan` and the implementer. This behavior assesses + sequences.
- Don't include test-only or generated files in any audit's input set. Tests inflate phantom counts and synthesize state that production never reaches.
- Don't extend `cap_findings` past 15. Plans longer than that become process documents, not action items.
- Don't run if there are uncommitted changes in the prompt assembly / pipeline runner / pipeline types files — the audit is a snapshot and uncommitted drift makes the snapshot meaningless.
