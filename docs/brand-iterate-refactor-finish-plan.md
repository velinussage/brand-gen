# brand-gen refactor finish plan

## Goal
Finish the post-monolith cleanup so the new package architecture is the true source of truth.

---

## Overall status
- [x] Thin CLI shim in `mcp/brand_iterate.py`
- [x] Package entrypoints (`python -m mcp.brand_iterate`, `brand-iterate`)
- [x] Command modules introduced
- [x] Compatibility shim preserved for `bgen ...`
- [x] RuntimeContext added and dispatch path can pass `args + ctx`
- [x] Internal tests migrated to package-first imports
- [x] Thin-entrypoint / registry parity / package-entrypoint tests added
- [x] Registry-driven parser generation
- [x] Registry-driven MCP tool generation
- [x] Move script-imported library code into package modules
- [x] Shrink/split `mcp/runtime.py`
- [x] Remove leftover duplicate command code
- [x] Update docs/tests to official entrypoints
- [x] Narrow compatibility scaffolding (`legacy_api.py` is external-only)

### Current validation snapshot
- ✅ `python3 -m py_compile ...`
- ✅ `python3 -m unittest discover -s tests -v` (`66` tests passing)

### Most important remaining architecture tradeoffs
1. **`legacy_api.py` remains only as an external compatibility shim.**
   Internal modules and tests now import concrete package modules directly.
2. **A small custom MCP surface still exists for non-CLI-backed behavior.**
   `brand_inspire` and `brand_pipeline` remain explicit custom handlers by design.
3. **Compatibility wrappers still exist under `scripts/*`.**
   Shared logic moved into `mcp/*`, but two script wrappers remain for backwards compatibility with direct script execution.

### Critical additions that were missing before this update
- [x] Explicit package-first execution status and compatibility shim status
- [x] Explicit `RuntimeContext` / `args + ctx` direction
- [x] Explicit note that `brand_iterate_mcp.py` should also become a thin adapter surface
- [x] Explicit internal-import migration item (`brand_iterate` helper imports → package modules / `legacy_api`)
- [x] Explicit validation snapshot so the plan reflects real execution status

---

# Phase 1 — Lock the architecture boundary
**Objective:** make the intended architecture explicit before more refactors.

**Status:** 🟢 Complete — code boundary and architecture notes are now in place.

## Tasks
- [x] Confirm official entrypoints:
  - `brand-iterate`
  - `python -m mcp.brand_iterate`
- [x] Keep `bgen ...` as compatibility-only
- [x] Ensure `mcp/brand_iterate.py` only re-execs package mode when run as `__main__`
- [x] Stop using `sys.path` mutation in the CLI entrypoint
- [x] Introduce `legacy_api.py` as the transitional compatibility surface for internal helper imports
- [x] Add/update a short architecture note in:
  - `CONTRIBUTING.md`
  - `docs/limitations.md`

## Acceptance criteria
- Entry-point policy is documented
- No new code imports business logic from `mcp.brand_iterate`

## Notes
- `brand_iterate.py` should stay tiny
- `legacy_api.py` is external compatibility only, not an internal destination

---

# Phase 2 — Make `command_registry.py` the real CLI source of truth
**Objective:** stop hand-maintaining parser structure separately.

**Status:** 🟢 Largely complete — parser creation now flows through `CommandSpec`-attached CLI builder callbacks and the dedicated `brand_gen/cli_builders.py` adapter.

## Tasks
- [x] Expand `CommandSpec` to carry parser metadata, not just handler/help/aliases
- [x] Add per-command argument-builder callbacks or declarative arg specs
- [x] Refactor `build_parser()` to derive subcommands from `COMMAND_SPECS`
- [x] Remove manual subparser duplication from `brand_gen/command_registry.py`
- [x] Add `dispatch_command(args, ctx)` support so command handlers can adopt `RuntimeContext` gradually
- [x] Convert the remaining giant argparse block into a CLI renderer instead of a second source of truth

## Acceptance criteria
- Adding a command means editing `CommandSpec` + handler + one CLI builder callback
- Parser subcommands are generated from the registry
- Aliases are still preserved

## Scratch notes
- Prefer:
  - semantic registry
  - CLI renderer
- Avoid:
  - giant argparse block plus registry side-by-side

## Update
- `brand_gen/cli_builders.py` now owns per-command CLI builder callbacks plus the CLI adapter.
- `brand_gen/command_registry.py` attaches `cli_builder` callbacks directly to each `CommandSpec`.
- `build_parser()` now delegates entirely to `build_cli_parser(COMMAND_SPECS, ...)`.
- Tests now assert every command spec has a callable CLI builder and that named commands are covered by the CLI builder registry.

---

# Phase 3 — Make MCP tool definitions registry-driven
**Objective:** eliminate CLI/MCP dual maintenance.

**Status:** 🟢 Largely complete — MCP tool definitions now come from the registry-backed bridge adapter for nearly all CLI-backed commands, and `brand_iterate_mcp.py` has been reduced to a thin server wrapper with only a tiny custom-tool surface.

## Tasks
- [x] Add MCP metadata to `CommandSpec` or a closely-related semantic tool spec:
  - tool name
  - description
  - input schema adapter or schema builder
- [x] Add a bridge registry for low-risk CLI-backed MCP tools
- [x] Generate a first batch of MCP tool schemas from parser introspection for read-only tools
- [x] Dispatch a first batch of MCP tools through generic argv assembly instead of hand-written branches
- [x] Create a dedicated MCP adapter/renderer from the semantic registry
- [x] Replace the remaining hand-maintained `TOOLS = [...]` bulk in `brand_gen/brand_iterate_mcp.py`
- [x] Make `brand_iterate_mcp.py` a thin compatibility/server shim, similar in spirit to `brand_iterate.py`
- [x] Keep any MCP-only special tools explicit if needed, but isolate them

## Acceptance criteria
- Most or all MCP tools come from the registry
- CLI command name and MCP mapping stay consistent
- `brand_iterate_mcp.py` stops being a huge schema dump

## Risks
- CLI args and MCP JSON inputs are related but not identical
- Use shared semantic specs, not forced identical structures

## Update
- `brand_gen/mcp_bridge_registry.py` now derives CLI-backed MCP tool specs from `COMMAND_SPECS`, parser introspection, and a small override table for tool-name compatibility, renamed MCP args, and schema/default tweaks.
- `brand_gen/brand_iterate_mcp.py` shrank from ~1900 lines to ~330 lines.
- Only `brand_inspire` and `brand_pipeline` remain custom MCP handlers because they are not pure CLI passthroughs.
- MCP tests now cover renamed-arg bridging (`brand_create`), generic generation bridging (`brand_generate`), and the invariant that only the two custom tools sit outside the bridge registry.

---

# Phase 4 — Move script-imported library code into the package
**Objective:** clean the package boundary.

**Status:** 🟢 Largely complete — shared helper logic moved into `mcp/*`, and `scripts/*` now only contains compatibility wrappers for direct execution.

## Current issue
Previously, `mcp/runtime.py` imported:
- `scripts.brand_scaffold`
- `scripts.load_inspiration_doctrine`

That package-boundary leak has now been removed.

## Tasks
- [x] Move reusable code from `scripts/brand_scaffold.py`
  - into package module, e.g. `mcp/brand_scaffold.py` or `mcp/brand_state.py`
- [x] Move reusable code from `scripts/load_inspiration_doctrine.py`
  - into package module, e.g. `mcp/inspiration_doctrine.py`
- [x] Leave only actual executable scripts under `scripts`
- [x] Update imports to package-relative imports
- [x] Add `scripts/__init__.py` so package-first execution works cleanly in the meantime

## Acceptance criteria
- No runtime package imports from `scripts.*`
- `/scripts` contains executables or thin compatibility wrappers, not shared library code

## Update
- Added package modules:
  - `mcp/brand_scaffold.py`
  - `mcp/inspiration_doctrine.py`
- `mcp/runtime.py` now imports those helpers via package-relative imports.
- `scripts/brand_scaffold.py` and `scripts/load_inspiration_doctrine.py` are now thin compatibility wrappers that forward to the package modules for direct script execution.
- Tests now assert `runtime.py` no longer imports shared logic from `scripts.*`.

---

# Phase 5 — Shrink and split `runtime.py`
**Objective:** avoid just relocating the monolith.

**Status:** 🟢 Largely complete — `runtime.py` is now a thin orchestration/compatibility layer and the helper families are split into focused runtime modules.

## Current status
- `mcp/runtime.py` is now `244` lines
- Focused runtime helper modules now exist:
  - `mcp/runtime_paths.py`
  - `mcp/runtime_io.py`
  - `mcp/runtime_brand.py`
  - `mcp/runtime_refs.py`
  - `mcp/runtime_models.py`

## Proposed sub-splits
- [x] `mcp/runtime_paths.py`
  - repo/script/data paths
  - constants
  - env locations
- [x] `mcp/runtime_io.py`
  - file/json/env helpers
- [x] `mcp/runtime_brand.py`
  - brand/session resolution helpers
- [x] `mcp/runtime_refs.py`
  - reference-path normalization/staging
- [x] `mcp/runtime_models.py`
  - material/model/aspect selection helpers

## Acceptance criteria
- [x] `runtime.py` becomes small orchestration/context only
- [x] Large helper families live in focused modules
- [x] No new god-module growth in `runtime.py`

## Rule of thumb
If a helper doesn’t need `RuntimeContext`, it probably shouldn’t live in `runtime.py`.

## Update
- Added new focused modules:
  - `mcp/runtime_paths.py`
  - `mcp/runtime_io.py`
  - `mcp/runtime_brand.py`
  - `mcp/runtime_refs.py`
  - `mcp/runtime_models.py`
- Rewrote `mcp/runtime.py` into a thin compatibility/orchestration layer that re-exports the focused modules plus a small number of wrappers for:
  - blackboard persistence
  - iteration memory
  - reference-analysis orchestration
  - VLM critique
- Repaired Phase 5 regression fallout by restoring `role_pack_material_key()` and the truncated `infer_material_type_from_filename()` path inside `runtime_models.py`.
- Added architecture regression coverage in `tests/test_project_layout.py` to assert the focused runtime modules exist and that helper families no longer live directly in `runtime.py`.

---

# Phase 6 — Remove leftover duplicate command code
**Objective:** finish normalization after the split.

**Status:** 🟢 Complete — command ownership has been normalized and is now regression-tested.

## Known issue
- [x] `cmd_review_brand` duplicate removed from `mcp/commands/references.py`
  - canonical owner: `mcp/commands/review.py`

## Tasks
- [x] Audit `mcp/commands/*.py` for duplicate `cmd_*`
- [x] Keep one owner per command
- [x] Update registry imports to point to canonical handler
- [x] Remove obsolete copies
- [x] Remove the old `brand_iterate` helper-import pattern from `pipeline_runner.py`
- [x] Remove the old `brand_iterate` helper-import pattern from `route_predicates.py`
- [x] Add a regression test so duplicate `cmd_*` handlers fail fast
- [x] Audit `brand_iterate_mcp.py` and remaining modules for direct helper imports; current direct imports are intentional thin-adapter dependencies

## Acceptance criteria
- Every command has exactly one handler
- Command ownership is obvious by module
- No ambiguous duplicates remain

## Update
- A duplicate-handler audit now reports **no duplicate `cmd_*` definitions** across `mcp/commands/`.
- `tests/test_command_registry.py` now enforces that invariant so future duplicate command owners fail CI immediately.

---

# Phase 7 — Update tests to enforce the new architecture
**Objective:** stop regressions.

**Status:** 🟢 Largely complete — AST guards, registry parity, MCP parity, and package-entrypoint tests are now in place.

## Tasks
- [x] Add entrypoint-thinness tests:
  - `brand_iterate.py` under a small line count target
  - no `cmd_*` in `brand_iterate.py`
- [x] Add AST guard:
  - no extracted helper families defined in `brand_iterate.py`
- [x] Add registry parity tests:
  - every `CommandSpec` has a handler
  - aliases resolve
  - CLI parser exposes the expected command surface
- [x] Add stronger proof that CLI parser is actually rendered from semantic registry metadata
- [x] Add MCP parity tests:
  - MCP tools derive from registry / MCP adapter
- [x] Update old tests away from direct top-level `brand_iterate` import assumptions where appropriate
- [x] Keep `legacy_api.py` tests only where transitional compatibility is intentional
- [x] Add package-entrypoint and legacy-shim subprocess tests

## Acceptance criteria
- [x] Architecture is enforced by tests
- [x] New commands cannot bypass registry pattern silently

## Update
- `tests/test_entrypoints.py` now enforces:
  - no business-logic imports in `mcp/brand_iterate.py`
  - no extracted helper-family definitions in `mcp/brand_iterate.py`
  - the shim only defines the re-exec helper and remains thin
- `tests/test_command_registry.py` now enforces:
  - parser choices cover all registry names and aliases
  - `build_parser()` delegates to the CLI adapter with `COMMAND_SPECS`
  - synthetic `CommandSpec` metadata can drive parser rendering without touching a manual argparse block
- A compatibility regression in `mcp.iteration_memory.build_iteration_memory_snippet()` was fixed while running the full architecture suite so the stricter tests can remain green.

---

# Phase 8 — Update docs to the official entrypoints
**Objective:** align the public surface with the actual architecture.

**Status:** 🟢 Complete — docs, skills, and tests now treat package-first entrypoints as the official path.

## Tasks
- [x] Update `README.md`
- [x] Update `docs/getting-started.md`
- [x] Update `docs/cli-reference.md`
- [x] Update `CONTRIBUTING.md`
- [x] Update primary skill files under `skills/`
- [x] Sweep remaining prompts/reference docs for package-first examples

## New preferred examples
- `brand-iterate ...`
- `python -m mcp.brand_iterate ...`

## Compatibility note
- Mention `bgen ...` is legacy-compatible, not preferred

## Acceptance criteria
- Docs no longer present file-path execution as the primary pattern

---

# Phase 9 — Remove or narrow compatibility scaffolding
**Objective:** reduce transitional clutter once consumers are migrated.

**Status:** 🟢 Complete — repo-internal imports were migrated off the shim, and the compatibility layer is now explicitly external-only.

## Tasks
- [x] Audit usage of `mcp/legacy_api.py`
- [x] Remove repo-internal imports that still depended on the shim
- [x] Deprecate remaining compatibility helpers intentionally
- [x] Decide whether `legacy_api.py` stays as a thin stable compatibility layer or is deleted

## Acceptance criteria
- Compatibility layer is intentional, minimal, and documented

---

# Recommended execution order
1. Phase 1
2. Phase 2
3. Phase 6
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 7
8. Phase 8
9. Phase 9

---

# Live scratchpad
## Now
- Focus: **Phase 2 / Phase 3 follow-through**

## Next
- **Phase 2 — keep parser generation fully registry-driven**
- **Phase 3 — keep MCP tool generation fully registry-driven**
- **Phase 7 — continue strengthening architecture tests**

## Blockers / watchouts
- CLI args and MCP schemas should share semantics, not necessarily identical structures
- `runtime_models.py` is now the largest runtime split module; keep pressure on future focused extraction instead of letting it become a second monolith
- session helper partials were a real regression source; keyword-only session APIs should stay enforced by tests

## Definition of done
- `brand_iterate.py` stays tiny
- parser is registry-driven
- MCP tool list is registry-driven
- no `scripts.*` imports in package runtime
- no duplicate `cmd_*`
- docs point to `brand-iterate` / `python -m mcp.brand_iterate`
- no repo-internal imports depend on `mcp.legacy_api`
- tests enforce architecture
