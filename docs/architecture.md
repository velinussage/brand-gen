# Architecture

## High-level flow

```text
route → plan-draft → critique-plan → build-generation-scratchpad → generate
```

The `pipeline` command runs this in one call for standard generative materials.

## State model

### Saved brand memory
- `.brand-gen/brands/<brand>/brand-profile.json`
- `.brand-gen/brands/<brand>/brand-identity.json`

### Session workspace
- `.brand-gen/sessions/<session>/brand-materials/`
- `manifest.json`
- `blackboard.json`
- `iteration-memory.json`
- `scratchpads/`
- `reviews/`

## Blackboard

The blackboard tracks:
- active brief
- recent decisions
- reference assignments
- generated asset lineage
- latest plan / critique / scratchpad paths

## Key commands

- `pipeline` — default one-call flow
- `show-session-summary` — fastest “what changed in this workspace?” summary
- `show-workflow-lineage` — lineage for a single `workflow_id`
