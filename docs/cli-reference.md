# CLI reference

Preferred entrypoints:

```bash
bgen ...
python3 -m brand_gen ...
```

Use `bgen --help` for the full command list and `bgen <command> --help` for command-level flags.

## Session start / onboarding

### Existing saved brand

```bash
bgen list-brands --format json
bgen use <brand-key>
```

Use `start-testing --brand <brand-key>` instead of `use` when you want an isolated sandbox.

### New saved brand from repo/docs

```bash
bgen init --brand-name acme
bgen extract-brand --project-root /path/to/project --brand-name acme
bgen use acme
```

Optional follow-ups:

```bash
bgen build-identity --profile /abs/path/to/brand-profile.json
bgen describe-brand --profile /abs/path/to/brand-profile.json
bgen validate-identity --format json
```

### No brand yet: create from conversation

```bash
bgen create-brand \
  --name Acme \
  --description "Operational software for modern field teams" \
  --tone "calm,technical" \
  --palette "#1A6B6B,#C85A2A"
```

Use `start-testing --working-name ...` instead if you want a temporary session sandbox before creating a durable saved brand.

## Identity / design-memory helpers

```bash
bgen parse-design-memory --path /path/to/project --format json
bgen extract-css-variables --path /path/to/project --format json
bgen diff-design-memory --before /path/old --after /path/new --format json
bgen show-identity --format json
```

## Core state / inspection

### `show-session-summary`

```bash
bgen show-session-summary --format json
```

### `context-snapshot`

Canonical machine-readable workspace snapshot for agents.

```bash
bgen context-snapshot --format json
```

### `workspace-status`

Canonical workspace root plus plugin/session alignment warnings.

```bash
bgen workspace-status --format json
```

### `capabilities`

Material/model/tool surface and feature flags.

```bash
bgen capabilities --format json
```

### `show-blackboard`

Shared specialist state plus learning summary / guardrails.

```bash
bgen show-blackboard --format json
```

### `show-reference-analysis` / `show-iteration-memory` / `show-workflow-lineage`

```bash
bgen show-reference-analysis --format json
bgen show-iteration-memory --format json
bgen show-workflow-lineage --workflow-id wf_123 --format json
```

## Planning primitives

### `route-request`

Route a brief before planning or generation.

```bash
bgen route-request --material-type x-feed --goal "Launch announcement" --format json
```

### `plan-material` / `plan-draft`

```bash
bgen plan-material --material-type x-feed --goal "Launch announcement" --format json
bgen plan-draft --material-type x-feed --goal "Launch announcement" --format json
```

### `critique-plan`

```bash
bgen critique-plan --plan /abs/path/to/plan-draft.json --format json
```

### `build-generation-scratchpad`

```bash
bgen build-generation-scratchpad --plan /abs/path/to/plan-draft.json --format json
```

### `resolve-prompt` / `review-prompt`

```bash
bgen resolve-prompt --plan /abs/path/to/plan.json --format json
bgen review-prompt --plan /abs/path/to/plan.json --format json
```

### `suggest-role-pack` / `suggest-layout`

```bash
bgen suggest-role-pack --material-type campaign-poster --format json
bgen suggest-layout --material-type x-feed --format json
```

## Generation

### `pipeline`

Run the full workflow: route → plan-draft → critique-plan → build-generation-scratchpad → generate.

```bash
bgen pipeline --material-type x-feed --mode hybrid --format json --open
```

Useful flags:

- `--goal "..."`
- `--source-version v017`
- `--route <route_key>`
- `--base-image /path/to/image`
- `--prompt-seed "..."`
- `--skip-route`
- `--critique-mode advisory`
- `--allow-blocking`
- `--open`

### Governed/source-derived HTML share cards on `pipeline`

Use `--render-backend html` for deterministic HTML-rendered share cards with plugin-based source fetching.

```bash
bgen pipeline \
  --material-type announcement-card \
  --render-backend html \
  --source-url "https://example.com/artifacts/<slug>" \
  --entity-type prompt \
  --proof-meta "UI systems" \
  --proof-meta "Typography" \
  --proof-row "Built for fast design decisions across product surfaces." \
  --design-variance 6 \
  --format json
```

Useful overrides:

- `--headline`
- `--subhead`
- `--cta`
- `--proof-title`
- `--proof-excerpt`
- `--proof-crop-path`
- `--skip-proof`
- `--dark-mode`
- `--layout-spec '{"columns":2,"proof_position":"right"}'`

### `generate`

Run a prepared scratchpad directly.

```bash
bgen generate --scratchpad /abs/path/to/scratchpad.json
```

### `generate-once`

Generate exactly one output from a scratchpad without any internal critique/refine loop.

```bash
bgen generate-once --scratchpad /abs/path/to/scratchpad.json --format json
```

## Set workflows

### `plan-set`

```bash
bgen plan-set --template launch-core --goal "New product launch" --format json
```

### `validate-brand-fit` / `validate-set`

```bash
bgen validate-brand-fit --set /abs/path/to/set.json --format json
bgen validate-set --set /abs/path/to/set.json --format json
```

### `generate-set`

```bash
bgen generate-set --set /abs/path/to/set.json --parallel
```

## Critique / review

### `critique-rubric`

```bash
bgen critique-rubric v12 --format json
```

### `submit-critique`

Default structured critique ingest path.

```bash
bgen submit-critique v12 --critique-json /abs/path/to/critique.json --format json
```

### `review-brand`

Build a critique/refine packet for a generated or composed asset.

```bash
bgen review-brand v17 --format json
```

### `feedback`

```bash
bgen feedback v17 --score 4 --notes "Strong direction"
bgen feedback v18 --score 1 --status rejected --notes "Generic, invented copy"
```

### `show` / `compare` / `diagnose`

```bash
bgen show --format json --latest 5
bgen compare --top 3
bgen diagnose v17 v18 --format json
```

## Messaging / learning

### `ideate-messaging` / `ideate-copy`

```bash
bgen ideate-messaging --format json
bgen ideate-copy --material-type social --goal "Launch announcement" --format json
```

### `update-messaging` / `promote-messaging`

```bash
bgen update-messaging --format json
bgen promote-messaging --format json
```

### `update-iteration-memory`

```bash
bgen update-iteration-memory --format json
```

### `improvement-questions` / `evolve`

```bash
bgen improvement-questions --format json
bgen evolve --format json
```

## Inspiration / references

### `extract-inspiration` / `consolidate-inspiration`

```bash
bgen extract-inspiration --category symbol
bgen consolidate-inspiration --format json
```

### `capture-product` / `shotlist`

```bash
bgen shotlist --product-name "Acme"
bgen capture-product --url https://example.com/app --label home --open-folder
```

### `explore-brand` / `example-sources` / `collect-examples`

```bash
bgen explore-brand --material x-feed --top 4 --format json
bgen example-sources --format json
bgen collect-examples --help
```

### `reference-rubric` / `submit-reference-analysis`

```bash
bgen reference-rubric --format json
bgen submit-reference-analysis --analysis-json /abs/path/to/analysis.json --format json
```

### `inspiration-mode` / `inspiration-list` / `inspiration-configure` / `inspiration-clear`

```bash
bgen inspiration-mode on
bgen inspiration-list --format json
bgen inspiration-configure --source <source-key>
bgen inspiration-clear
```

## Discovery / utilities

```bash
bgen types
bgen social-specs
bgen prompts-list --format json
bgen prompts-get replicate/image-workflow.md --format json
```
