# Getting started

This guide takes you from clone to a first generated asset and a usable workspace.

## 1. Clone and configure

```bash
git clone <your-fork-or-repo-url>
cd brand-gen
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e .
cp .env.example .env
```

Add your Replicate token to `.env`, install `agent-browser` if you have not already, then validate:

```bash
python3 scripts/validate_setup.py
```

Notes:

- The repo-local `.env` is the preferred config source.
- A legacy `~/.claude/.env` fallback is still supported for compatibility.
- Set `BRAND_GEN_DIR` in `.env` if you want durable state outside the repo checkout.

## 2. Understand where state will live

The runtime stores durable state under `.brand-gen/` (or whatever `BRAND_GEN_DIR` points to).

Useful checks:

```bash
bgen workspace-status --format json
bgen capabilities --format json
```

`workspace-status` is the best quick check when you are not sure which brand/session/root is active.

## 3. Choose the correct onboarding path

### A. Existing saved brand

If the brand already exists in `.brand-gen/brands/`:

```bash
bgen list-brands --format json
bgen use <brand-key>
```

If you want a sandboxed exploration instead of mutating the saved brand directly:

```bash
bgen start-testing \
  --session-name first-social-pass \
  --brand <brand-key> \
  --goal "Create a product-led social card"
```

### B. New brand from a project repo/docs bundle

If the user has a real product repo, docs export, design-memory bundle, or reference assets:

```bash
bgen init --brand-name acme
bgen extract-brand \
  --project-root /path/to/project \
  --brand-name acme
bgen use acme
```

Optional follow-ups:

```bash
bgen describe-brand --profile /abs/path/to/brand-profile.json
bgen validate-identity --format json
```

### C. No brand yet — start from conversation

If there is no repo/docs bundle and the brand is still being defined:

```bash
bgen create-brand \
  --name "Acme" \
  --description "Operational software for modern field teams" \
  --tone "calm,technical,trustworthy" \
  --palette "#1A6B6B,#C85A2A"
```

This scaffolds a saved brand, writes a minimal valid `brand-profile.json`, builds `brand-identity.json`, and makes the new brand active.

Use `start-testing` instead only when you explicitly want a temporary sandbox before saving durable brand memory.

## 4. Check the current workspace state

```bash
bgen show-session-summary --format json
bgen context-snapshot --format json
```

Use `show-session-summary` after each major step. Use `context-snapshot` when another tool/agent needs a machine-readable view of the active workspace.

## 5. If copy matters, ideate messaging first

```bash
bgen ideate-messaging --format json
bgen ideate-copy --material-type x-feed --goal "Launch announcement" --format json
```

These commands return context and scaffolding for the agent to turn into real messaging/copy options.

## 6. Generate a first asset

```bash
bgen pipeline \
  --material-type x-feed \
  --goal "Launch announcement" \
  --mode hybrid \
  --format json
```

If you want to iterate from an existing version:

```bash
bgen pipeline --material-type x-feed --source-version v001 --format json
```

## 7. Optional: use the manual planning primitives

Use these when you want to inspect each stage instead of calling `pipeline`:

```bash
bgen route-request --material-type x-feed --goal "Launch announcement" --format json
bgen plan-material --material-type x-feed --goal "Launch announcement" --format json
bgen plan-draft --material-type x-feed --goal "Launch announcement" --format json
bgen critique-plan --plan /abs/path/to/plan-draft.json --format json
bgen build-generation-scratchpad --plan /abs/path/to/plan-draft.json --format json
bgen generate --scratchpad /abs/path/to/scratchpad.json
```

Manual mode is especially useful when you want to review route choice, role-pack selection, or prompt assembly before rendering.

## 8. Review what changed

```bash
bgen show-session-summary --format json
bgen show --format json --latest 3
bgen compare --top 3
```

`compare` is the fastest way to inspect version history visually.

## 9. Review with the modern critique flow

```bash
bgen critique-rubric v1 --format json
bgen submit-critique v1 --critique-json /abs/path/to/critique.json --format json
```

The default path is rubric → agent/human review → `submit-critique`. The legacy internal VLM critique loop remains explicit opt-in only.

## 10. Score and iterate

```bash
bgen review-brand v1 --format json
bgen feedback v1 --score 4 --notes "Strong direction, simplify the copy"
bgen evolve --format json
```

Preferred CLI entrypoints: `bgen ...` or `python3 -m brand_gen ...`.

## 11. Extend the session

```bash
bgen consolidate-inspiration --format json
bgen derive-video --source-version v1 --format json
bgen derive-mockup --source-version v1 --format json
bgen plan-set --template launch-core --goal "New product launch" --format json
```

Use `consolidate-inspiration` to build reusable inspiration memory. Use derivatives only after you have an approved still worth extending. Use set planning when the request is really a coordinated family of materials.
