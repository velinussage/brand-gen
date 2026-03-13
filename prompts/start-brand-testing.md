# Start Brand Testing

Use this prompt to begin a new brand-gen exploration before any generation.

## Intent

We are starting a **testing session**, not assuming a saved brand by default.

Choose one:
- create a temporary working brand from interviews and exploration
- seed the session from an existing saved brand

## Reverse interview

Answer these before planning material generation:

1. What brand or product are we actually testing?
2. Is this a temporary working brand or an existing saved brand?
3. What should remain recognizable right now?
4. What feels wrong or too weak in the current brand outputs?
5. What surfaces matter first?
   - landing hero
   - product visual
   - social card
   - motion
   - poster
6. What should the work feel like?
7. What should it definitely not feel like?
8. What would make the next output obviously better?

## Then do this

1. Start the session:
```bash
python3 mcp/brand_iterate.py start-testing --session-name <name> --working-name "<name>" --goal "<goal>"
```
Or seed from a saved brand:
```bash
python3 mcp/brand_iterate.py start-testing --session-name <name> --brand acme --goal "<goal>"
```

2. Inspect current identity memory:
```bash
python3 mcp/brand_iterate.py show-identity --show-prelude
python3 mcp/brand_iterate.py show-blackboard
```

3. Route + ideate:
```bash
python3 mcp/brand_iterate.py route-request --material-type <material> --goal "<goal>" --request "<brief>"
python3 mcp/brand_iterate.py ideate-material --material-type <material> --mode hybrid
```

4. Draft + critique:
```bash
python3 mcp/brand_iterate.py plan-draft --material-type <material> --mode hybrid --mechanic "<mechanic>"
python3 mcp/brand_iterate.py critique-plan --plan <draft.json>
```

5. Build execution:
```bash
python3 mcp/brand_iterate.py build-generation-scratchpad --plan <draft.json>
python3 mcp/brand_iterate.py generate --scratchpad <scratchpad.json>
```

6. Generate only when the draft is critiqued and the scratchpad is clean.
