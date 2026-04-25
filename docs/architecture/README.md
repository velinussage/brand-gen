# Brand-gen architecture docs

This directory is the repo-local architecture home for brand-gen runtime contracts. Keep these docs inside the brand-gen checkout so `.pi`, Claude, OpenClaw, MCP, and CLI adapter changes have one nearby source of truth.

## Current contracts

- `runtime-agent-contract.md` — canonical host/agent runtime rules.
- `tool-groups/orchestration.md` — stage tools and scratchpad assembly.
- `tool-groups/mutation.md` — typed mutation tools that replace direct file edits.
- `tool-groups/inspection-policy.md` — read-only inspection and policy status tools.
- `source-knowledge.md` — brand-scoped Obsidian/docs ingestion contract.
- `social-prompt-tuning.md` — v123 Sage social prompt tuning notes.
- `gepa-dspy-optimization.md` — GEPA/DSPy optimization plan and disagreement-record schema.
- `aesthetic-curation.md` — curated style/moodboard capsules and brand-local aesthetic preferences.

When agent prompts need to stay short, link here instead of copying long procedures into `.pi/agents/*.md`.
