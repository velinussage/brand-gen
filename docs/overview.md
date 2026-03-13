# Overview

brand-gen is a local, file-backed toolkit for AI-agent-led brand material experimentation.

It combines:
- stored brand memory (`brand-profile.json`, `brand-identity.json`)
- session memory (`iteration-memory.json`)
- planning-first generation
- manifest/version tracking
- CLI + MCP interfaces

## What it is for

Use brand-gen when you want an agent to:
1. understand a brand and product before prompting
2. choose the right onboarding path (saved brand, extracted brand, or no-brand-yet session)
3. plan a material instead of jumping straight to generation
4. accumulate copy, messaging, and visual learnings over time
5. generate and compare multiple versions with explicit feedback

## Important skills

- `brand-gen` — main skill; use for almost every normal session
- `brand-gen-reference` — load only when you need model/surface/file-layout reference material
- `brand-gen-logo` — use when the task is a logo / wordmark / lockup workflow

## Core value

brand-gen works best when the agent treats the brand as evolving memory, not as a static adjective list.
