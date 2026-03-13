# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- One-call `pipeline` command — runs route → plan → critique → scratchpad → generate with workflow_id correlation
- Messaging iteration loop — `ideate-messaging`, `update-messaging`, `promote-messaging` commands
- Typed pipeline schemas (`pipeline_types.py`) with dataclass contracts
- Scored predicate routing (`route_predicates.py`) — replaces keyword-based classification
- Session summary command (`show-session-summary`) — one-call workspace state inspection
- Iteration memory with separate note buckets: brand, messaging, copy
- Brand identity schema v2 with full messaging section
- Prompt budget enforcement for interface materials (~1800 char resolved limit)
- Reference count discipline (2 refs max for interface materials)
- Agent skill files consolidated to 3 files (brand-gen, brand-gen-reference, brand-gen-logo)

### Changed
- `ideate-messaging` returns context assembly (no nested LLM calls) — the calling agent generates angles
- `compress_prompt_body` tightened for interface materials (400 chars, was 700)
- Inspiration doctrine capped at 350 chars for interface materials (was 600)
- Material DNA defaults are now brand-agnostic (no hardcoded product names)

### Fixed
- `cmd_update_iteration_memory` double-write bug — each `--kind` now routes to exactly one bucket
- `promote-messaging` bucket flattening — `positioning_insights` and `copy_insights` kept separate
