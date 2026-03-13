# Skills

brand-gen intentionally exposes three public skills.

## `brand-gen`

Use this first for almost every session.

What it covers:
- the correct onboarding path at session start
- deciding whether to use `pipeline`, step-by-step planning, set workflows, or messaging-first flows
- the main CLI/MCP command reference
- session lifecycle and agent-readable outputs

### Onboarding logic inside `brand-gen`

1. **Existing saved brand?** Use `list-brands` and either `use <brand-key>` or `start-testing --brand <brand-key>`.
2. **Repo/docs bundle exists but no saved brand yet?** Use `init --brand-name`, then `extract-brand`, then `use`.
3. **No brand yet at all?** Use `start-testing --working-name`, gather product truth from conversation, write the session profile, and rebuild identity with `build-identity`.

## `brand-gen-reference`

Load this only when you need reference material, not workflow guidance.

What it covers:
- model selection guidance
- social/feed surfaces and dimensions
- workspace file layout

## `brand-gen-logo`

Use this only for logo, wordmark, or lockup workflows.

What it covers:
- batch logo iteration
- silhouette-preserving vs exploratory logo flows
- review/feedback loop for marks
