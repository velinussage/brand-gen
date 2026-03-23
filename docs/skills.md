# Skills

brand-gen exposes six public skills under `skills/`.

Hosts can either:

- read these skill folders directly from the repo checkout, or
- copy them into a host-specific skill directory when the host requires local installation

Prefer loading only the smallest skill set that matches the current job.

## `brand-gen-setup`

Use this first for a brand-gen install or host-wiring task.

It covers:

- repo clone and Python environment setup
- `.env` configuration and validation
- MCP server registration
- host-specific wiring notes for Claude Code, Pi, OpenClaw, and CLI-first agents

After setup is complete, load `brand-gen` for normal usage.

## `brand-gen`

Use this first for almost every brand-material session.

What it covers:

- the correct onboarding path at session start
- deciding whether to use `pipeline`, manual planning primitives, set workflows, or messaging-first flows
- the main CLI/MCP command surface
- session lifecycle and agent-readable outputs
- the default critique flow (`critique-rubric` → `submit-critique`)
- current state surfaces such as `show-session-summary`, `context-snapshot`, `workspace-status`, and `show-blackboard`

### Onboarding logic inside `brand-gen`

1. **Existing saved brand?** Use `list-brands` and either `use <brand-key>` or `start-testing --brand <brand-key>`.
2. **Repo/docs bundle exists but no saved brand yet?** Use `init --brand-name`, then `extract-brand`, then `use`.
3. **No brand yet at all?** Use `create-brand --name ... --description ... --tone ... --palette ...` for a durable brand, or `start-testing --working-name` only when you want a temporary sandbox first.

## `brand-gen-orchestration`

Load this when you want the full 6-phase generation pipeline on top of the core workflow skill.

What it covers:

- prepare → plan → validate → generate → critique → evolve
- quality-gated generation with explicit plan review
- design-philosophy and source-vault guidance
- learning-loop and critique expectations for iterative sessions

Load `brand-gen` first, then add `brand-gen-orchestration` when you want the stricter pipeline.

## `brand-gen-reference`

Load this only when you need reference material, not workflow guidance.

What it covers:

- model selection guidance
- social/feed surfaces and dimensions
- workspace file layout
- command gotchas and file-layout specifics

## `brand-gen-logo`

Use this only for logo, wordmark, or lockup workflows.

What it covers:

- batch logo iteration
- silhouette-preserving vs exploratory logo flows
- review/feedback loop for marks

## `brand-content-ideation`

Use this when the user needs help deciding messaging, copy, campaign framing, or content direction before generation.

What it covers:

- messaging and narrative exploration
- copy angle generation
- campaign/content-system ideation
- shaping what the material should say before deciding how it should look
