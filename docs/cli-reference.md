# CLI reference

## Session start / onboarding

### Existing saved brand
```bash
python3 mcp/brand_iterate.py list-brands --format json
python3 mcp/brand_iterate.py use <brand-key>
```

Use `start-testing --brand <brand-key>` instead of `use` when you want an isolated sandbox.

### New saved brand from repo/docs
```bash
python3 mcp/brand_iterate.py init --brand-name acme
python3 mcp/brand_iterate.py extract-brand --project-root /path/to/project --brand-name acme
python3 mcp/brand_iterate.py use acme
```

### No brand yet: create from conversation
```bash
python3 mcp/brand_iterate.py create-brand \
  --name Acme \
  --description "Operational software for modern field teams" \
  --tone "calm,technical" \
  --palette "#1A6B6B,#C85A2A"
```

Use `start-testing --working-name ...` instead if you want a temporary session sandbox before creating a durable saved brand.

Use `show-session-summary --format json` immediately after onboarding to confirm the active workspace.

### `create-brand`
Create a saved brand from a conversational brief and scaffold a valid profile + identity.

```bash
python3 mcp/brand_iterate.py create-brand --name "Acme" --description "Operational software for modern field teams" --tone "calm,technical" --palette "#1A6B6B,#C85A2A"
```


## Most-used commands

### `pipeline`
Run the full generative workflow.

```bash
python3 mcp/brand_iterate.py pipeline --material-type x-feed --mode hybrid --format json
```

### `show-session-summary`
See generated versions, feedback, messaging, iteration notes, and latest artifacts.

```bash
python3 mcp/brand_iterate.py show-session-summary --format json
```

### `show`
Inspect manifest entries.

```bash
python3 mcp/brand_iterate.py show --format json --latest 5
python3 mcp/brand_iterate.py show v3 --format json
```

### `ideate-messaging`
Returns context for the agent to generate positioning angles.

```bash
python3 mcp/brand_iterate.py ideate-messaging --format json
```

### `update-messaging`
Persist approved tagline, elevator, voice, and copy-bank items.

```bash
python3 mcp/brand_iterate.py update-messaging --tagline "..." --add-headline "..." --format json
```

### `review-brand`
Build a review packet with critique prompts plus a provisional score suggestion the agent can ask the user to confirm.

```bash
python3 mcp/brand_iterate.py review-brand --version v17
```

### `plan-set` / `validate-set` / `generate-set`
Use for coordinated multi-material campaigns.


### `diagnose`
Compare prompt length, prelude size, refs, critic issues, and workflow lineage across versions.

```bash
python3 mcp/brand_iterate.py diagnose v14 v20 --format json
```


### `compare`
Build the HTML comparison board. With no explicit versions it now works well as a history view, and each card includes a copyable prompt for asking your agent to regenerate from that version with a new screen or new input.

```bash
python3 mcp/brand_iterate.py compare --all
python3 mcp/brand_iterate.py compare --latest 12
```
