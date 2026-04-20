# Claude Code agents for brand-gen

Seven specialist subagents that port brand-gen's pi-subagent pipeline to Claude Code's native agent system. Each agent drives one phase of the 6-phase brand-orchestrator workflow.

| Agent | Role | Default model |
|---|---|---|
| `brand-orchestrator` | Default entry point; coordinates the full 6-phase pipeline | `claude-opus-4-7` |
| `brand-explorer` | Read-only workspace / brand-state reporting | `claude-sonnet-4-6` |
| `brand-router` | Route selection (reference / inspiration / hybrid / set / motion) | `claude-sonnet-4-6` |
| `brand-planner` | Plan-draft authoring with learnings + role-pack + layout prep | `claude-opus-4-7` |
| `brand-critic` | Plan critique + post-generation image critique, AI-slop gate | `claude-opus-4-7` |
| `brand-generator` | Scratchpad assembly and generation execution | `claude-sonnet-4-6` |
| `brand-philosopher` | Cultivates the brand's design philosophy from vault + identity | `claude-opus-4-7` |

## Install

Pick one. All three options work; `A` and `B` leave the brand-gen repo untouched.

### A. Project-scoped adoption (recommended — per-project opt-in)

In the project where you want these agents available:

```bash
mkdir -p .claude/agents
cp path/to/brand-gen/skills/brand-gen/claude-agents/brand-*.md .claude/agents/
```

Claude Code auto-discovers agents from `.claude/agents/` in the project root.

### B. User-scoped adoption (every Claude Code session on this machine)

```bash
mkdir -p ~/.claude/agents
cp path/to/brand-gen/skills/brand-gen/claude-agents/brand-*.md ~/.claude/agents/
```

### C. Working inside the brand-gen repo itself

The brand-gen repo already ships `.claude/agents/brand-*.md` at the repo root. Nothing to copy — Claude Code picks them up when you run it from this directory. Precedence is project → user → plugin, so the project copy always wins.

## Invoke

Claude Code dispatches agents via the `Agent` tool with `subagent_type`:

```
Agent(
  subagent_type="brand-orchestrator",
  description="Generate concept illustration",
  prompt="Material type: concept-illustration. Purpose: ..."
)
```

Or via natural language delegation: *"spawn a brand-critic to score v057 and record feedback."*

## Model overrides

Frontmatter sets a default model per agent. Callers can override per-dispatch by asking the agent to use a specific model in the delegation prompt, or you can edit the frontmatter directly.

If you're also using **pi**, model overrides live in `.pi/settings.json` under `subagents.agentOverrides`. See brand-gen's root `.pi/settings.json` for the pattern.

## What the pi → Claude Code port preserves and loses

**Preserved:**
- The 6-phase pipeline contract (prepare → plan → validate → generate → critique → evolve)
- Every agent's workflow narrative — the markdown bodies are verbatim from `.pi/agents/`
- Tool allowlists per role (explorer/router are read-only; planner/critic/generator can Bash)
- Model tiers (sonnet for discovery/exec, opus for judgment)

**Lost in translation (Claude Code has no equivalent):**
- `/chain agent1 -> agent2` with automatic `{previous}` variable handoff — simulate with explicit file writes (e.g. explorer writes `/tmp/brand-snapshot.json`, planner reads it).
- `/parallel` fan-out with named slots — Claude Code only has experimental Agent Teams.
- `--bg` background dispatch with polling — Agent tool is synchronous.
- `systemPromptMode: replace` + `inheritProjectContext: false` — Claude Code agents always append to the base prompt and always inherit `CLAUDE.md` and discovered skills.
- `reasoning_effort` / `thinking` frontmatter level — use Claude Code's model-specific thinking settings instead.

## Handoff pattern without chain

Without `/chain`, agents hand off via the filesystem:

```
brand-explorer  → writes brand-snapshot.json
brand-planner   → reads brand-snapshot.json, writes plan-<id>.json via `bgen plan-draft --output`
brand-critic    → reads plan-<id>.json, writes critique-<id>.json via `bgen critique-plan --output`
brand-generator → reads both, runs `bgen build-generation-scratchpad` + `bgen generate`
```

This is slower than pi's in-memory chain but has the advantage that every intermediate is inspectable.

## Keep in sync

When `.pi/agents/brand-*.md` changes in brand-gen, re-run the copy. The two directories are intentional mirrors — one for pi, one for Claude Code. Frontmatter differs (Claude Code uses tool arrays, Claude model IDs, and drops pi-only fields like `reasoning_effort`); the markdown body is identical.
