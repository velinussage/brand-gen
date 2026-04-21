# Command Reference

Current CLI + MCP cheatsheet for brand-gen.

## Naming rule

Most commands follow:

```text
bgen <command-name>  →  brand_<command_name>
```

Important exceptions:

- `list-brands` → `brand_list`
- `create-brand` → `brand_create`
- `extract-brand` → `brand_extract`
- `build-identity` → `brand_build_identity`
- `describe-brand` → `brand_describe`
- `review-brand` → `brand_review`
- `pipeline` → `brand_pipeline`
- `inspire` → `brand_inspire`

## Pipeline & generation

### `pipeline`

- **CLI**: `bgen pipeline --material-type <material> --mode hybrid --format json`
- **MCP**: `brand_pipeline(material_type="<material>", mode="hybrid")`
- **Returns**: route, draft, critique, scratchpad, generation result, `workflow_id`, `stopped_at`, lineage fields
- **Useful flags**: `--source-version`, `--route`, `--base-image`, `--prompt-seed`, `--goal`, `--allow-blocking`, `--critique-mode`, `--open`
- **Gotcha**: `stopped_at == "critique"` means blocked before generation

### `generate`

- **CLI**: `bgen generate --scratchpad <scratchpad.json>`
- **MCP**: `brand_generate(scratchpad="/abs/path/to/scratchpad.json")`
- **Use when**: you already inspected the plan and want to run a prepared scratchpad directly

### `generate-once`

- **CLI**: `bgen generate-once --scratchpad <scratchpad.json> --format json`
- **MCP**: `brand_generate_once(scratchpad="/abs/path/to/scratchpad.json")`
- **Use when**: you want exactly one generation pass with no internal critique/refine loop

### `generate-set`

- **CLI**: `bgen generate-set --set <set.json> --parallel`
- **MCP**: `brand_generate_set(set="/abs/path/to/set.json")`
- **Gotcha**: validate the set before generating

## Share cards

### HTML share cards

- **CLI**:

```bash
bgen pipeline \
  --material-type announcement-card \
  --render-backend html \
  --source-url "https://example.com/artifacts/<slug>" \
  --entity-type prompt \
  --format json
```

- **MCP**: `brand_pipeline(material_type="announcement-card", render_backend="html", source_url="...", entity_type="prompt")`
- **Useful overrides**: `--headline`, `--subhead`, `--cta`, `--proof-title`, `--proof-excerpt`, `--proof-row`, repeated `--proof-meta`, `--proof-crop-path`, `--skip-proof`, `--dark-mode`, `--design-variance`, `--layout-spec`
- **Gotcha**: requires Chrome for headless PNG rendering

## Planning & routing

### `route-request`

- **CLI**: `bgen route-request --material-type <material> --goal "<goal>" --format json`
- **MCP**: `brand_route_request(material_type="<material>", goal="<goal>", request="<brief>")`
- **Returns**: selected route and candidates

### `plan-material` / `plan-draft`

- **CLI**:
  - `bgen plan-material --material-type <material> --format json`
  - `bgen plan-draft --material-type <material> --format json`
- **MCP**:
  - `brand_plan_material(...)`
  - `brand_plan_draft(...)`

### `critique-plan`

- **CLI**: `bgen critique-plan --plan <draft.json> --format json`
- **MCP**: `brand_critique_plan(plan="/abs/path/to/draft.json")`
- **Returns**: checks, blocking issues, warnings, recommendations

### `build-generation-scratchpad`

- **CLI**: `bgen build-generation-scratchpad --plan <draft.json> --format json`
- **MCP**: `brand_build_generation_scratchpad(plan="/abs/path/to/draft.json")`

### `resolve-prompt` / `review-prompt`

- `resolve-prompt --plan <plan.json> --format json`
- `review-prompt --plan <plan.json> --format json`

### `suggest-role-pack` / `suggest-layout`

- `suggest-role-pack --material-type <material> --format json`
- `suggest-layout --material-type <material> --format json`

## Critique & review

### `critique-rubric`

- **CLI**: `bgen critique-rubric v12 --format json`
- **MCP**: `brand_critique_rubric(version="v12")`
- **Returns**: image path + critique rubric (v1 packet by default; v2 packet when `--dspy-scorer`)
- **Useful flags**:
  - `--dspy-scorer` — run the DSPy vision scorer inline and embed axis scores, rationales, overall decision, disqualifier check, and `why_user_might_dislike_if_polished`. Requires `pip install -e '.[scoring]'` + `OPENROUTER_API_KEY`.
  - `--scorer-model <model>` — override the judge LM (default: `openrouter/anthropic/claude-haiku-4.5`; also supports `openrouter/anthropic/claude-sonnet-4.5`, direct `anthropic/...` routing, etc.)

### `submit-critique`

- **CLI**: `bgen submit-critique v12 --critique-json /path/to/critique.json --format json`
- **MCP**: `brand_submit_critique(version="v12", critique_json="/path/to/critique.json")`
- **Minimum payload**: `approved`, `p1`

### `reference-rubric` / `submit-reference-analysis`

- `reference-rubric --format json`
- `submit-reference-analysis --analysis-json /path/to/analysis.json --format json`

### `review-brand`

- **CLI**: `bgen review-brand v17 --format json`
- **MCP**: `brand_review(version="v17")`
- **Returns**: review packet and suggested score; persist only after user confirmation

## Brand setup & management

### `init`

- create `.brand-gen/`
- optionally scaffold a brand key

### `create-brand`

- **CLI**: `bgen create-brand --name "<name>" --description "..." --tone "..." --palette "..."`
- **MCP**: `brand_create(...)`
- preferred for conversation-first onboarding

### `extract-brand`

- **CLI**: `bgen extract-brand --project-root <path> --brand-name "<name>"`
- **MCP**: `brand_extract(...)`
- use when a repo/docs bundle exists

### `start-testing`

- create a sandboxed session workspace
- use with `--brand <brand-key>` to seed from an existing saved brand

### `use` / `list-brands` / `build-identity` / `validate-identity` / `types`

- `use <brand-key>` — switch active saved brand
- `list-brands --format json` — list saved brands
- `build-identity --profile <profile.json>` — rebuild identity from profile
- `validate-identity --format json` — inspect identity completeness
- `types` — list material types and default models/ARs

## Messaging & ideation

- `ideate-messaging --format json`
- `ideate-copy --material-type <material> --goal "..." --format json`
- `ideate-material --format json`
- `update-messaging --format json`
- `promote-messaging --format json`

## Inspection & state

- `show-session-summary --format json`
- `context-snapshot --format json`
- `workspace-status --format json`
- `capabilities --format json`
- `show-blackboard --format json`
- `show --format json --latest 5`
- `compare --top 6`
- `diagnose v14 v15 --format json`
- `show-workflow-lineage --workflow-id <id> --format json`
- `show-reference-analysis --format json`
- `show-iteration-memory --format json`
- `show-rubric --material-type <type> --format json` — dump the v2 rubric axes + material overlay + disqualifier rule from `brand_gen/scoring/rubric_registry.py`
- `show-disagreements [--bucket <bucket>] [--material-type <type>] [--partition-tag holdout_a|holdout_b] [--limit N] --format json` — list scored agent-vs-user disagreements from the brand's `scoring/disagreements.jsonl`
- `scoring-status --format json` — disagreement-bucket counts, partition split, and weighted Cohen's kappa (quadratic weights) + raw agreement rate when enough data is present

## Inspiration, product capture, and design memory

- `brand_inspire(...)` — flexible MCP convenience tool for inspiration capture/list/configuration
- `extract-inspiration`
- `consolidate-inspiration`
- `inspiration-mode`
- `example-sources`
- `collect-examples`
- `shotlist`
- `capture-product`
- `explore-brand`
- `social-specs`
- `parse-design-memory`
- `extract-css-variables`
- `diff-design-memory`

## Derivatives, feedback, and learning

- `derive-video --source-version v17 --format json`
- `derive-mockup --source-version v17 --format json`
- `plan-set --template <template> --format json`
- `validate-brand-fit --set <set.json> --format json`
- `validate-set --set <set.json> --format json`
- `feedback v17 --score 4 --notes "..."`
- `evolve --format json`
- `improvement-questions --format json`
- `update-iteration-memory --format json`
