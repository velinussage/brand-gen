# Getting started

This guide takes you from clone to a first generated social card.

## 1. Clone and configure

```bash
git clone <your-fork-or-repo-url>
cd brand-gen
cp .env.example .env
```

Add your Replicate token to `.env`, then validate:

```bash
python3 scripts/validate_setup.py
```

## 2. Choose the correct onboarding path

### A. Existing saved brand
If the brand already exists in `.brand-gen/brands/`:

```bash
python3 mcp/brand_iterate.py list-brands --format json
python3 mcp/brand_iterate.py use <brand-key>
```

If you want a sandboxed exploration instead of mutating the saved brand directly:

```bash
python3 mcp/brand_iterate.py start-testing \
  --session-name first-social-pass \
  --brand <brand-key> \
  --goal "Create a product-led social card"
```

### B. New brand from a project repo/docs bundle
If the user has a real product repo, docs export, or reference bundle:

```bash
python3 mcp/brand_iterate.py init --brand-name "acme"
python3 mcp/brand_iterate.py extract-brand \
  --project-root /path/to/project \
  --brand-name "acme"
python3 mcp/brand_iterate.py use acme
```

### C. No brand yet — start from conversation
If there is no repo/docs bundle and the user is still defining the brand, the fastest path is:

```bash
python3 mcp/brand_iterate.py create-brand \
  --name "Acme" \
  --description "Operational software for modern field teams" \
  --tone "calm,technical,trustworthy" \
  --palette "#1A6B6B,#C85A2A"
```

This scaffolds a saved brand, writes a minimal valid `brand-profile.json`, builds `brand-identity.json`, and makes the new brand active.

Use `start-testing` instead when you explicitly want a temporary sandbox before saving anything durable:

```bash
python3 mcp/brand_iterate.py start-testing \
  --session-name first-social-pass \
  --working-name "Acme" \
  --goal "Create a product-led social card"
```

## 3. Check current workspace state

```bash
python3 mcp/brand_iterate.py show-session-summary --format json
```

## 4. If copy matters, ideate messaging first

```bash
python3 mcp/brand_iterate.py ideate-messaging --format json
```

The command returns context plus instructions; the agent reads that context and generates 3–5 positioning angles.

## 5. Generate a first asset

```bash
python3 mcp/brand_iterate.py pipeline \
  --material-type x-feed \
  --mode hybrid \
  --format json
```

## 6. Review what changed

```bash
python3 mcp/brand_iterate.py show-session-summary --format json
python3 mcp/brand_iterate.py show --format json --latest 3
```

## 7. Score and iterate

```bash
python3 mcp/brand_iterate.py feedback v1 --score 4 --notes "Strong direction, simplify the copy"
python3 mcp/brand_iterate.py compare --top 3
python3 mcp/brand_iterate.py evolve
```
