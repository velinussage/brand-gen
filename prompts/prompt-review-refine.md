# Prompt Review + Refine

Use this before generating when a brand-gen prompt is:

- too long
- too abstract
- too screenshot-biased
- too contaminated by the wrong references
- too generic to produce a branded result

## Goal

Turn a long resolved prompt into a shorter generation prompt that:

1. preserves brand truth
2. preserves product truth when required
3. uses translated references as mechanics only
4. contains one clear visual move

## Minimal loop

```bash
python3 mcp/brand_iterate.py resolve-prompt --plan <draft-or-plan.json>
python3 mcp/brand_iterate.py review-prompt --plan <draft-or-plan.json>
python3 mcp/brand_iterate.py build-generation-scratchpad --plan <draft-or-plan.json>
python3 mcp/brand_iterate.py generate --scratchpad <scratchpad.json>
```

## Good prompt shape

1. short brand truth
2. short material rule
3. compact reference translation summary
4. one direct art-direction ask

## Bad prompt shape

- tech stack
- repeated palette lists
- repeated “do not” clauses
- poster/sticker doctrine inside browser prompts
- no explicit reference roles

## Review questions

- What is the one hero moment?
- What are we preserving?
- What are we pushing?
- Which references are actually shaping composition?
- What gets removed from the prompt?
