# Brand Review + Refine Loop

Inspired by:
- Compound Engineering's review/refine workflow
- Compound Knowledge's parallel reviewer model
- Every's social-clips narrative-arc pattern

Use this after generating or composing any serious brand artifact, especially:
- landing heroes
- social cards
- X feed visuals
- product banners
- browser illustrations

## Core idea

Do not go straight from generation to approval.

Run a short **critique → merge → refine** loop:
1. review the artifact from multiple angles
2. group findings by severity
3. make one substantive change
4. re-review

## Parallel reviewers

Run these lenses independently, then merge:

### 1. Strategic/message reviewer
Questions:
- Is the core claim understandable in under five seconds?
- Is the promise specific, or generic enough to belong to any SaaS tool?
- Does the artifact answer "what is this?" and "why care?"

### 2. Copy/voice reviewer
Questions:
- Does the headline carry the real promise?
- Does the subheadline add information rather than repeat?
- Are CTAs clear, concrete, and appropriately ranked?
- Does the copy sound like the right brand?

### 3. Composition/balance reviewer
Questions:
- What dominates first: copy or product?
- Is that the correct hierarchy?
- Does the whitespace feel intentional?
- Does the product visual support the message instead of competing with it?

### 4. Fidelity reviewer
Questions:
- Is the real product still intact?
- Were presentation references used only for framing and polish?
- Were fake UI labels, buttons, or cards introduced?

## Severity buckets

### P1 — Blocks shipping
- unclear or misleading core message
- hero/product balance so poor that the artifact is hard to parse
- product truth broken

### P2 — Should fix
- weak differentiation
- repetitive or soft copy
- CTA hierarchy unclear
- trust row not proving anything

### P3 — Nice to have
- minor wording polish
- small spacing/rhythm adjustments
- subtle visual cleanup

## Refine rule

After review:
- auto-fix obvious P3 issues
- choose **one** P1 or P2 issue as the next refinement
- make the single change
- re-review

Do not make five big changes at once.

## Landing hero copy pattern

Borrow the social-clips idea of a clear spine:

1. **Hook** — eyebrow or headline opening
2. **Promise** — what the product gives you
3. **Proof** — trust row, product moment, or concrete cue
4. **Action** — CTA

For a landing hero:
- eyebrow = category / frame
- headline = promise
- subheadline = clarifying proof
- trust row = credibility
- CTA = action

## Operational flow

```bash
python3 mcp/brand_iterate.py review-brand v11
```

After review, turn the critique into a score recommendation before the next generation:

```text
## Feedback proposal

- Best version: v11
- Suggested score: 4/5
- Status: favorite
- Why: strongest message hierarchy, best brand anchor, least hallucinated UI/copy

- Reject version: v9
- Suggested score: 1/5
- Status: rejected
- Why: generic promise, broken product truth, weak brand recognition
```

Then persist only the user-confirmed judgment:

```bash
python3 mcp/brand_iterate.py feedback v11 --score 4 --status favorite --notes "Strongest hierarchy; keep this calmer direction."
python3 mcp/brand_iterate.py feedback v9 --score 1 --status rejected --notes "Invented copy and weak product truth."
```

Scoring rubric:
- **5** = near-ship / clearly best direction
- **4** = strong direction worth preserving
- **3** = mixed, informative but not a lock
- **2** = weak, keep only narrow lessons
- **1** = reject / negative example

Then have the agent produce:

```text
## Review: v11

### P1 — Blocks shipping
...

### P2 — Should fix
...

### P3 — Nice to have
...

### Clean
...

### Next refinement
[One change to make next, and why.]
```
