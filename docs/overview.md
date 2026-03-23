# Overview

brand-gen is a local, file-backed runtime for AI-agent-led brand material work.

It combines:

- durable brand memory (`brand-profile.json`, `brand-identity.json`)
- testing sessions and saved-brand workspaces under `.brand-gen/`
- blackboard state, iteration memory, manifests, review packets, and run artifacts
- planning-first generation and rubric-first critique
- HTML share cards, derivatives, and inspiration memory
- CLI, MCP, and host-plugin surfaces backed by the same runtime

## What it is for

Use brand-gen when you want an agent to:

1. understand a brand and product before prompting
2. choose the right onboarding path (saved brand, extracted brand, or no-brand-yet session)
3. plan a material or set instead of jumping straight to generation
4. accumulate messaging, review, and visual learnings over time
5. work inside a durable workspace that other hosts/plugins can inspect later

## Where state lives

The core workspace is `.brand-gen/`.

- `brands/<brand>/` — durable saved brand memory
- `sessions/<session>/brand-materials/` — testing-session workspace
- `config.json` — active brand/session selectors
- `runtime-status/plugins/*.json` — host-plugin status markers

Host plugins such as Pi and OpenClaw usually point at a shared root like `~/.brand-gen`, while direct CLI use can stay repo-local or be redirected with `BRAND_GEN_DIR`.

## Important skills

- `brand-gen-setup` — first-time install and host wiring
- `brand-gen` — default workflow for most sessions
- `brand-gen-reference` — reference material only, not workflow guidance
- `brand-gen-logo` — logo / wordmark / lockup workflows
- `brand-content-ideation` — messaging, copy, and content direction before generation

## Core value

brand-gen works best when the agent treats the brand as evolving memory, not as a one-off adjective list.
