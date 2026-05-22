# brand-gen agent contract

This file tells AI agents (Claude Code, pi, openclaw, Cursor, Continue, etc.) how to mutate brand state in this repository. Read this before editing any file under `brand_gen/`, `data/`, or `.brand-gen/brands/<brand>/`.

## The hybrid pattern

Brand state lives in two shapes, mutated through two channels:

| Shape | Where | Mutated by | Audit |
|---|---|---|---|
| **Prose direction** — paragraph-shaped voice, framings, art direction, adoption scenes | `.brand-gen/brands/<brand>/voice/*.md`, `.brand-gen/brands/<brand>/custom-scratchpad.md`, `.brand-gen/brands/<brand>/iteration-memory.md`, `.brand-gen/brands/<brand>/brand-identity.md` | Agent `Edit` / `Write` directly; human-curated; review-on-merge gate | git history |
| **Structured constraints** — atomic items in lists, schema-locked configs | `data/aesthetic_capsules.json`, `data/sage_brand_contract.json`, `.brand-gen/brands/<brand>/custom-scratchpad.json`, `.brand-gen/brands/<brand>/aesthetic-preferences.json`, `.brand-gen/brands/<brand>/iteration-memory.json` | Typed `bgen` mutation verbs ONLY | `<brand>/mutations.jsonl` ledger |

Generation events stay in `.brand-gen/brands/<brand>/runs/<workflow_id>.jsonl` (per-workflow). State mutations go to `.brand-gen/brands/<brand>/mutations.jsonl` (per-brand, append-only).

## Never-edit rules

These are hard rules. Violations break prompt assembly invariants.

1. **Never put brand-payload literals in `brand_gen/*.py`.** No new `SAGE_*`, `<BRAND>_*`, or brand-coupled constants. The mechanism is brand-agnostic; payload lives in JSON or markdown.
2. **Never hand-edit `.brand-gen/brands/<brand>/<contract>.json` or `data/*_brand_contract.json`.** Use the typed verb. The only exception is during a verb-development PR.
3. **Never edit `data/aesthetic_capsules.json` directly.** Use `bgen add-aesthetic-capsule`.
4. **Never write to `<brand>/mutations.jsonl` or `<brand>/runs/*.jsonl`.** They are append-only audit logs. Verbs and the pipeline runner write to them; nothing else.
5. **Read-only-after-launch markdown:** if a `voice/*.md` file has frontmatter `read_only_after: <git-sha>`, edits require human review. The verbose CLI greeting will warn agents about this.

## Mutation verb table

All typed mutation verbs flow through `bgen <verb>`. Each verb writes a `state_mutation` event to `<brand>/mutations.jsonl` with `verb`, `target_path`, `before_hash`, `after_hash`, `diff_summary`, `reason`, and `source_version`.

| Verb | Mutates | Use for |
|---|---|---|
| `add-aesthetic-capsule` | `data/aesthetic_capsules.json` | Add or update an aesthetic capsule (style register / moodboard handle). |
| `append-forbidden-pattern` | `<brand>/custom-scratchpad.json` | Add a hard-banned phrase or pattern to the active brand. |
| `append-custom-scratchpad-note` | `<brand>/custom-scratchpad.md` | Add a bullet under a markdown section (`global` / `motion` / `typography` / `composition`). Prose-shaped notes also accepted via direct `Edit`; prefer the verb when the note belongs in a known section so it dedupes. |
| `set-motion-grammar` | `<brand>/custom-scratchpad.{json,md}` | Set the structured motion grammar (director, favored, banned, intensity). |
| `update-palette` | `<brand>/brand-identity.json` | Update palette tokens; reruns WCAG audit. |
| `update-typography` | `<brand>/brand-identity.json` | Update typography roles. |
| `update-devices` | `<brand>/brand-identity.json` | Add or remove approved graphic devices. |
| `update-iteration-memory` | `<brand>/iteration-memory.{md,json}` | Record positive/negative examples or notes. |
| `promote-learning` | `<brand>/learnings.json` | Promote a typed learning entry into the active brand learnings memory. |
| `promote-aesthetic-learning` | `<brand>/aesthetic-preferences.json` | Record an aesthetic capsule like/dislike. |
| `promote-style-policy` | `<brand>/learnings.json` | Promote a structured style-reference policy. |
| `submit-review` | `<brand>/reviews/<version>-agent-review.json` | Submit an agent review packet for a generated artifact. |

Run `bgen <verb> --help` for full argument list. All verbs accept `--dry-run`, `--reason`, and `--source-version`.

## Files agents may freely Edit

Markdown files under `.brand-gen/brands/<brand>/` not marked `read_only_after`:

- `custom-scratchpad.md` — section bullets (prefer the verb for `global`/`motion`/`typography`/`composition`)
- `iteration-memory.md` — running notes
- `brand-identity.md` — descriptive prose (NOT structured tokens; use `update-palette` etc. for those)
- `voice/*.md` — framing directions, default scenes, style anchors (created by PR-2)
- `agents/*.agent.md` — host-neutral agent specifications. Prose specifications may be edited; host overlays and tool allowlists are compiled into mirrors via `scripts/sync_agents.py`.

Markdown files at the repo root that document the system (`README.md`, `AGENTS.md` itself, prompt-pack `*.md`) are normal source; edit through PRs.

## Files agents must NOT freely Edit

- `.claude/agents/*.md`, `.pi/agents/*.md`, `skills/brand-gen/claude-agents/*.md` — auto-generated mirrors. Never edit these directly; make changes in `agents/*.agent.md` and run `scripts/sync_agents.py`.
- `brand_gen/*.py` — no new brand-payload literals (see Never-edit rule #1)
- `data/aesthetic_capsules.json` — go through `add-aesthetic-capsule`
- `data/sage_brand_contract.json` (and any future `data/<brand>_brand_contract.json`) — go through the typed verb (see PR-1)
- `.brand-gen/brands/<brand>/custom-scratchpad.json` — go through `append-forbidden-pattern` / `set-motion-grammar`
- `.brand-gen/brands/<brand>/brand-identity.json` — go through `update-palette` / `update-typography` / `update-devices`
- `.brand-gen/brands/<brand>/aesthetic-preferences.json` — go through `promote-aesthetic-learning`
- `.brand-gen/brands/<brand>/learnings.json` — go through `promote-learning` / `promote-style-policy`
- `.brand-gen/brands/<brand>/runs/*.jsonl` — append-only audit; written by the pipeline only
- `.brand-gen/brands/<brand>/mutations.jsonl` — append-only audit; written by mutation verbs only

## Why this pattern

Field convergence (2024-2026): markdown for prose direction (Claude Skills, AGENTS.md / Linux Foundation Dec 2025, Cursor `.cursor/rules/*.mdc`, Continue `.continue/rules/*.md`, aider `CONVENTIONS.md`), schema-bound JSON + typed mutation verbs for structured state (LangGraph `Annotated[list, operator.add]` reducers, OpenAI Agents SDK).

ETH Zurich 2025 found LLM-generated guidance docs *reduced* task success ~3% and increased inference cost >20%. So prose direction wants a human edit gate; agents read but don't freely rewrite. Constraint mutations get a typed reducer and an audit log.

## Dual-write contract (markdown + JSON pairs)

Several brand workspace files exist as paired `.json` (canonical) + `.md`
(rendered) files:

| Pair | Canonical | Rendered | Re-render verb |
|---|---|---|---|
| `iteration-memory.{json,md}` | `.json` | `.md` | `bgen render-iteration-memory` |
| `brand-identity.{json,md}` | `.json` | `.md` | `bgen build-identity` (regenerates from profile) |

Rule: **JSON is canonical. Markdown is a derived view.** Never edit the
markdown directly — those edits will be overwritten on the next save.
After mutating the JSON via a typed verb (`update-palette`,
`update-iteration-memory`, etc.), the markdown is rewritten in the same
call. If you suspect drift (markdown out of sync with JSON), run the
re-render verb above.

A round-trip test (`tests/test_iteration_memory_roundtrip.py`) asserts
this property in CI.

## When the rules conflict with what you need

If a typed verb is missing for a structured-state edit you need, the right move is to **add the verb** (mirror `add-aesthetic-capsule` in `brand_gen/commands/state.py` + `cli_builders.py` + `command_registry.py`), not hand-edit the JSON. Hand-edits leave no `mutations.jsonl` record and break the audit invariant.

If a markdown file is `read_only_after`, write your proposed change as a comment in a related untracked scratchpad file, surface it in the PR description, and let a human merge it.
