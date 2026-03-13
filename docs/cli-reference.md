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

### No brand yet: conversation-first session
```bash
python3 mcp/brand_iterate.py start-testing --session-name exploration --working-name Acme --goal "Find the first strong branded direction"
python3 mcp/brand_iterate.py build-identity \
  --profile .brand-gen/sessions/exploration/brand-materials/brand-profile.json \
  --output-json .brand-gen/sessions/exploration/brand-materials/brand-identity.json \
  --output-markdown .brand-gen/sessions/exploration/brand-materials/brand-identity.md
```

Use `show-session-summary --format json` immediately after onboarding to confirm the active workspace.

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

### `plan-set` / `validate-set` / `generate-set`
Use for coordinated multi-material campaigns.
