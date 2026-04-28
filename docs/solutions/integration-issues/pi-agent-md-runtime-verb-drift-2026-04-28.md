---
title: "Pi/Claude agent .md files reference unregistered runtime tools"
date: 2026-04-28
track: bug
category: integration-issues
problem_type: contract-drift
module: ".pi/agents, .claude/agents"
status: resolved
severity: medium
related_files:
  - .pi/agents/brand-planner.md
  - .pi/agents/brand-router.md
  - .pi/agents/brand-orchestrator.md
  - tests/
tags:
  - "agent-contracts"
  - "runtime-drift"
  - "mcp-tools"
  - "regression-tests"
  - "pi-agents"
---

## Problem

The agent definitions in `.pi/agents/*.md` and `.claude/agents/*.md` describe tool calls and pick roles in prose. When the runtime tool surface changes (verb count grew 25 → 40 → 44 over recent weeks), the markdown drifts. Agents then call non-existent verbs, pass deprecated arg names, or fall back to bash workarounds that bypass the typed-tool schemas — silent quality regression.

## Symptoms

- Pi orchestrator calls `brand_review_run({"run_id": "..."})` — runtime requires `version_id`. Hard error.
- Pi planner attempts `pick style=<version>` — `style` is not a valid `pick` role; valid set is `composition / motif / application / motion / product_truth`.
- Orchestrator calls `brand_plan_run` with no args; `material_type` was not enforced in the .md contract.
- Bash fallback executor "works around" typed-tool mismatches — the typed verbs (with schemas) are bypassed and quality drops without an error trail.
- `.claude/agents/brand-planner.md` and `.pi/agents/brand-planner.md` describe slightly different schemas.

## What didn't work

- **Periodic manual review of agent docs** — drift compounds faster than reviews catch it.
- **Comments inside markdown referencing old verbs** — agents read prose, not commentary.
- **Vague prose** ("call review with the version") — pattern-matched to whatever the LLM saw in training, often a stale signature.

## Solution

Defensive repetition + explicit "do not" rules anchored to the runtime contract, plus a regression test that fails when frontmatter drifts.

**1. Explicit hard rules in agent prose.** In `.pi/agents/brand-orchestrator.md`:

```
5. brand_review_run — call with version_id: <version_id> and workflow_id: <run_id>
   when known. Do not call with run_id only; the current runtime requires version_id.

Never call brand_review_run with run_id alone. Required minimum:
{"version_id":"v214","workflow_id":"..."}
```

In `.pi/agents/brand-planner.md`:

```
Never use `pick style=<version>`; valid roles are
composition, motif, application, motion, product_truth.
```

**2. Frontmatter-vs-runtime test.** Apr 24 regression test asserts every tool name in `.pi/agents/*.md` frontmatter is registered in the canonical MCP schema, and asserts Pi registers all 44 canonical `brand_*` verbs. This is the durable fix — drift is now caught before deploy. (session history)

## Why this works

Agent definitions are runtime instructions to a stochastic process. Vague prose pattern-matches to stale training data. Explicit allowlists with "Do not call with X" survive that. A test that the frontmatter matches the registry is the only thing that catches new drift introduced by future verb additions.

## Prevention

- Any time you rename a tool argument or change a required field, grep `.pi/agents/` and `.claude/agents/` for the old name before merging.
- New verbs/roles get added to the hard-rules block in every agent that calls them, with the valid set enumerated.
- Cross-check `.pi/agents/*.md` against `.claude/agents/*.md` — divergence is drift.
- Keep the verb count in sync between Pi runtime and agent docs. Stale numbers (25-verb / 40-verb references) in older docs are a leading indicator. (session history)

## Pattern signal

```
brand_review_run.*run_id                  # missing version_id
pick style=                                # invalid role
"tools:".*<tool not in mcp schema>        # frontmatter drift
```

Cross-check Pi and Claude agent files for the same agent name. Identical-looking descriptions with subtly different schemas mean drift is in flight.
