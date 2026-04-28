---
title: "Product-truth validator self-triggers on its own ban field"
date: 2026-04-28
track: bug
category: runtime-errors
problem_type: validator-self-trigger
module: brand_gen/product_truth.py
status: resolved
severity: high
related_files:
  - brand_gen/product_truth.py
tags:
  - "validator"
  - "product-truth"
  - "negation-detection"
  - "self-blocking"
  - "word-boundary"
---

## Problem

The Sage product-truth validator scanned plan text for banned terms (`Prompt Pack`, `System of Provenance`, `fake app screen`). When those terms appeared inside a guardrail field — e.g. a prompt seed reading `"No QR code, source URL block, ..., or fake app screen"` — the validator counted them as affirmative invented-taxonomy hits and blocked the run. The contract prelude itself ("avoid Prompt Pack") tripped its own contract validator.

## Symptoms

- `validate_product_truth_plan` returns `invented_product_taxonomy` errors that quote terms the plan was forbidding.
- `_FAKE_PRODUCT_SCREEN_RE` ("fake app screen") fires inside long ban lists.
- Substring match: `Prompt Pack` matches inside `Prompt Packed Brief`.
- Substring match: `static` matches inside `state…`.

## What didn't work

- **Fixed-width 6-word negation prefix window** (`_NEGATED_TERM_PREFIX_RE` later expanded to 32 tokens) — long comma-chained ban lists overflowed the window between the lone "no" cue and the term.
- **Substring matching with no word boundary** — caused the `static`/`state` and `Prompt Pack`/`Prompt Packed` collisions.
- **Excluding the `ban` field entirely (initial pass)** — solved the self-trigger but lost validation of user-supplied `push` lists that mentioned banned terms in negative context.

## Solution

Three reinforcing fixes in `brand_gen/product_truth.py`:

1. **Drop `ban` from the haystack** — `plan_product_truth_haystack()` (lines ~155-180) explicitly excludes `ban`:
   ```python
   # `ban` is deliberately excluded: product-truth validators care about
   # affirmative intent, not terms that appear only in "avoid/no/ban X"
   # guardrails. Including the ban list caused the Sage contract itself
   # ("no Prompt Pack...") to trip the invented-taxonomy blocker.
   parts.extend(_as_text(plan.get(field)) for field in ("preserve", "push"))
   ```

2. **Sentence-scoped negation fallback** in `_is_negated_mention()` — when the fixed prefix window misses, walk back to the nearest sentence boundary (`.!?\n;`) and treat the segment as negated if any negation cue (`no`, `not`, `avoid`, `ban`, …) appears without a contrastive turn (`but`, `instead show`, …) afterward.

3. **Word-boundary regex** in `_affirmative_term_hits()`:
   ```python
   pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", flags=re.IGNORECASE)
   ```

## Why this works

Affirmative-intent detection is a negation-aware NLP task with three independent failure modes. Haystack composition decides what *can* be flagged at all (field exclusion). Word boundaries decide what counts as a token. Sentence-bounded negation decides what to discount. Each layer fails on a different mode; all three are needed.

## Prevention

When a validator scans free-text policy fields:

- Decide per-field whether content is affirmative intent or negative guardrail; exclude the latter from the haystack.
- Always require word boundaries: `(?<![\w-])X(?![\w-])`, never bare `re.escape(term)`.
- Use sentence-bounded negation, not fixed token windows; check for contrast cues (`but`, `instead`, `rather`) after the negation cue.
- The Apr 26 morning patch (negation-window expansion) was insufficient on its own. The real fix is structured `avoid=…` clauses + sentence-bounded fallback + word boundaries together. (session history)

## Pattern signal

Grep for these to detect this class of bug:

```
re.compile(r".*\b(no|not|avoid|ban).*\{0,N\}"   # fixed-window negation
re.escape(term).*IGNORECASE                       # term match without word boundaries
\.lower\(\) in haystack                           # substring match in policy haystacks
```

If a validator's haystack includes a `ban` / `avoid` / `forbid` field, that's the smell.
