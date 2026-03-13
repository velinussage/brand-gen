# openclaw-brand-gen

OpenClaw plugin bridge for `<brand-gen-repo>`.

Current implementation focus:
- Phase 1 foundation: MCP bridge, config parsing, code-mode tools, brand context injection
- Phase 2 memory layer: SQLite journal + JSON learnings
- Phase 3 first pass: heartbeat scheduling, discover/generate cycle, orphan cleanup, deterministic generation policy
- backend-backed discover source enforcement via `brand_explore --source`
- approval-aware heartbeat gating with pending output review tracking

Not yet complete:
- deeper inspiration capture/crawl freshness logic
- richer approval queueing beyond `approvalMode`
- persistent degraded-health summaries / operator surfaces
