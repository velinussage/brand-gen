# Workspace file layout

## Primary state

- `.brand-gen/config.json` — active saved brand + active session pointers
- `.brand-gen/brands/<brand>/brand-profile.json` — saved brand profile
- `.brand-gen/brands/<brand>/brand-identity.json` — saved brand identity
- `.brand-gen/sessions/<session>/brand-materials/` — active testing workspace

## Per-workspace artifacts

- `manifest.json` — generated versions + feedback
- `blackboard.json` — active brief, recent decisions, generated asset lineage
- `iteration-memory.json` — brand/copy/messaging/material notes and positive/negative examples
- `scratchpads/` — saved plan drafts, critiques, prompt reviews, and generation scratchpads
- `reviews/` — auto-review outputs

## Best inspection commands

- `show-session-summary --format json` — one-call summary of current workspace state
- `show-blackboard --format json` — route/decision/artifact state
- `show-workflow-lineage --workflow-id <id>` — cross-stage lineage for one pipeline run
- `show VERSION` — manifest entry for one generated version
