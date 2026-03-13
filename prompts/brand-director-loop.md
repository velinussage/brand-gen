# Brand Director Loop

Use brand-gen as a supervisor + specialist system.

## Goal
Move one material through:
1. route
2. plan draft
3. critique
4. generation scratchpad
5. execution
6. post-generation review

## Shared state
The source of truth is `blackboard.json` inside the active brand workspace.
Every specialist should read it before acting and write back one concise decision after acting.

## Specialist roles
- **Brand Director** — chooses route, keeps the loop aligned with user goals
- **Identity Strategist** — clarifies brand truth, anchors, and permitted drift
- **Copy Strategist** — slogans, headlines, CTAs, voice
- **Visual Composer** — refs, model routing, prompt building, deterministic composition
- **Critic Agent** — P1/P2/P3 review before and after generation

## Hard rules
- No hidden default brand
- No fake lockups
- No generation without a generation scratchpad
- No promotion to the next step when P1 issues remain
- Keep the blackboard current
