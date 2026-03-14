---
name: brand-gen
description: >
  Main skill for brand-gen. Use this for almost every brand-material session: start or inspect the
  active workspace, iterate messaging, run the one-call pipeline, or drop to step-by-step planning
  when the user wants explicit reasoning.
compatibility:
  tools: [Bash, Read, Write]
---

# Brand Gen

Use this as the default skill for brand-gen.

## First: choose the right onboarding path

Before generating anything, decide whether this session is:
1. a **saved brand** that already exists,
2. a **new brand extracted from a repo/docs bundle**, or
3. a **no-brand-yet exploration** that should start as a testing session.

### Step 0 — ensure `.brand-gen/` exists

```bash
python3 mcp/brand_iterate.py init --brand-name "<optional-brand-key>"
```

Use `init` to create the shared workspace. If you already know the intended saved brand key,
pass it here so the folder exists under `.brand-gen/brands/<key>/`. `init` now scaffolds a minimal
`brand-profile.json` + `brand-identity.json` so the saved brand is immediately usable.

### Path A — use an existing saved brand

Check what already exists:

```bash
python3 mcp/brand_iterate.py list-brands --format json
```

Then choose one of two modes:

#### A1. Work directly against the saved brand
Use this when the user wants to continue from the canonical brand memory and does **not** need an isolated sandbox.

```bash
python3 mcp/brand_iterate.py use <brand-key>
python3 mcp/brand_iterate.py show-session-summary --format json
```

#### A2. Seed a testing session from the saved brand
Use this when the user wants to explore variants without mutating the saved brand directly.

```bash
python3 mcp/brand_iterate.py start-testing \
  --session-name "<session-name>" \
  --brand <brand-key> \
  --goal "<what this session should learn or produce>"
```

This copies the saved brand into `.brand-gen/sessions/<session>/brand-materials/` and makes the session active.

### Path B — no saved brand, but there is a repo/docs bundle

Use this when the user has a product repo, docs export, or reference bundle that can be mined for brand truth.

```bash
python3 mcp/brand_iterate.py init --brand-name "<brand-key>"
python3 mcp/brand_iterate.py extract-brand \
  --project-root <path-to-product> \
  --brand-name "<brand-key>"
python3 mcp/brand_iterate.py use <brand-key>
```

This is the cleanest onboarding path because it creates reusable saved-brand memory first.

### Path C — no brand yet, start from conversation

Use this when there is no repo/docs bundle and the user is still forming the brand.

Fast durable path:

```bash
python3 mcp/brand_iterate.py create-brand \
  --name "<brand-name>" \
  --description "<what the product is and who it serves>" \
  --tone "calm,technical,trustworthy" \
  --palette "#1A6B6B,#C85A2A"
```

This creates `.brand-gen/brands/<key>/`, writes a minimal valid `brand-profile.json`, builds `brand-identity.json`, and makes the new brand active.

Use `start-testing` instead only when you explicitly want a temporary sandbox before saving a durable brand:

```bash
python3 mcp/brand_iterate.py start-testing \
  --session-name "exploration" \
  --working-name "<brand-name>" \
  --goal "figure out the first good branded materials"
```

Testing-session path:
1. start the testing session,
2. write or edit the session `brand-profile.json` directly,
3. rebuild the session identity from that file,
4. generate inside the session,
5. promote durable messaging or manually copy the session memory into a saved brand later.

```bash
python3 mcp/brand_iterate.py build-identity   --profile .brand-gen/sessions/<session>/brand-materials/brand-profile.json   --output-json .brand-gen/sessions/<session>/brand-materials/brand-identity.json   --output-markdown .brand-gen/sessions/<session>/brand-materials/brand-identity.md
```

### Resume the current context

At any point, the fastest “where am I and what state exists?” command is:

```bash
python3 mcp/brand_iterate.py show-session-summary --format json
```

Use it to confirm:
- current workspace kind (`saved_brand` vs `session`)
- seeded-from brand, if any
- recent generations and feedback
- current messaging state
- latest blackboard artifacts

## Routing decision tree

```text
User wants to generate a material?
├─ Standard generative (browser-illustration, banner, social, animation)
│  └─ pipeline
├─ Logo / wordmark / lockup exploration?
│  └─ load brand-gen-logo
├─ Material set / campaign family?
│  └─ plan-set → validate-set → generate-set
├─ User wants explicit reasoning between stages?
│  └─ route-request → plan-draft → critique-plan → build-generation-scratchpad → generate
└─ User wants to discuss positioning or copy first?
   └─ ideate-messaging → update-messaging → ideate-copy → then generate
```

## Fast session lifecycle

### Session start
1. Run the onboarding path above: existing saved brand, repo/docs extraction, or no-brand-yet testing session.
2. Check workspace state: `show-session-summary --format json`.
3. For copy-bearing materials, run `ideate-messaging --format json` before generating.
4. Run `show-blackboard` to see the latest active brief, decisions, and artifacts.

### Session end
1. `promote-messaging --include-copy-notes` if positioning/copy improved.
2. `show-session-summary` to review generations, scores, notes, and messaging.
3. `show-iteration-memory` only if you need the raw note buckets.

## Scoring and feedback

Scoring is how brand-gen turns a one-off generation session into reusable memory.

### The rule

- **Final numeric scores should reflect user preference**, not silent agent guesswork.
- The agent **can propose** a score or favorite based on conversation ("this one is closest", "reject that one", "I like the calmer direction"), but should only write canonical feedback when the user intent is explicit enough.

### Current write path

```bash
python3 mcp/brand_iterate.py feedback v17 --score 4 --notes "Strong direction, simplify the copy"
python3 mcp/brand_iterate.py feedback v17 --status favorite
python3 mcp/brand_iterate.py feedback v18 --score 1 --status rejected --notes "Feels generic and the copy is invented"
```

MCP equivalent:

- `brand_feedback(version="v17", score=4, notes="...", status="favorite")`

### How to think about scores

- **5** = should strongly shape future work; near-ship or best-in-session
- **4** = clearly good direction; preserve major traits and refine
- **3** = mixed; useful signal but not a direction to lock in
- **2** = weak; keep only narrow lessons from it
- **1** = reject; use as a negative example

### What the agent should do

After compare/review, summarize preference like this:

```text
Best candidate: v17
Suggested score: 4/5
Why: strongest brand anchor, calmer field, copy closest to approved messaging

Reject: v18
Suggested score: 1/5
Why: invented copy, weak product truth, too generic
```

Then write `feedback` only when the user has clearly endorsed or rejected the direction.

### Why this matters

Scores feed:
- manifest ranking
- positive / negative examples in iteration memory
- future `evolve` analysis
- stronger prompt shaping over time

Unscored generations are basically lost learning.

## What I can see vs what I can't

- Best agent-readable outputs: commands with `--format json`, especially `pipeline`, `route-request`, `plan-draft`, `critique-plan`, `build-generation-scratchpad`, `ideate-messaging`, `ideate-copy`, `show-session-summary`, `show-blackboard`, and `show`.
- I can reason over images only if they are passed to me as files/paths; I cannot see what is currently on the user's screen.
- Avoid user-facing folder-opening flows when agent-readable JSON exists; prefer `show-session-summary`, `show`, or `compare` metadata first.

## Command reference

Each entry shows **CLI + MCP**, the **return shape**, and the main **gotcha**.

### pipeline
- **When**: default for standard generative work.
- **CLI**: `python3 mcp/brand_iterate.py pipeline --material-type <material> --mode hybrid --format json`
- **MCP**: `brand_pipeline(material_type="<material>", mode="hybrid")`
- **Returns**: route, draft, critique, scratchpad, generation result, `workflow_id`, `stopped_at`.
- **Gotcha**: `stopped_at == "critique"` means blocked before generation; inspect blocking checks instead of retrying blindly.

### pipeline with base image (edit/overlay)
- **When**: user provides an existing image and wants branded overlays, text, icons, or edits on top of it.
- **CLI**: `python3 mcp/brand_iterate.py pipeline --material-type podcast-cover --base-image /path/to/photo.jpg --prompt-seed "Add title bar with Intro to Sage and pillar mark icon" --format json`
- **MCP**: `brand_pipeline(material_type="podcast-cover", base_image="/path/to/photo.jpg", prompt_seed="Add title bar with Intro to Sage and pillar mark icon")`
- **What happens**: auto-selects `flux-2-pro` (multi-reference editing model). The base image is passed as the primary input; any brand reference assets (mark, icon) are passed as additional references. The prompt instructs the model what to add/overlay.
- **Extra references**: pass stored brand assets via `--image` alongside `--base-image` — e.g. the pillar mark PNG as a reference so the model knows exactly what icon to place.
- **Gotcha**: prompt should use instruction language ("Add X to Y", "Place Z in bottom-left") not descriptive language ("A poster with X and Y"). The model edits the existing image rather than generating from scratch.

### route-request
- **When**: user wants reasoning visible before planning.
- **CLI**: `python3 mcp/brand_iterate.py route-request --material-type <material> --goal "<goal>" --request "<brief>" --format json`
- **MCP**: `brand_route_request(material_type="<material>", goal="<goal>", request="<brief>")`
- **Returns**: route key, route metadata, score vector.
- **Gotcha**: use this when the user asks *why this path?*; otherwise `pipeline` is cheaper.

### plan-draft
- **When**: you need an editable plan before critique.
- **CLI**: `python3 mcp/brand_iterate.py plan-draft --material-type <material> --mode hybrid --format json`
- **MCP**: `brand_plan_draft(material_type="<material>", mode="hybrid")`
- **Returns**: plan-draft JSON payload (and optionally saved path when `--output` is used).
- **Gotcha**: prefer `--format json`; otherwise you may only get a path/message and need another read.

### critique-plan
- **When**: before building a scratchpad from a draft/plan.
- **CLI**: `python3 mcp/brand_iterate.py critique-plan --plan <draft.json> --format json`
- **MCP**: `brand_critique_plan(plan="/abs/path/to/draft.json")`
- **Returns**: checks, blocking issues, warnings, recommendations.
- **Gotcha**: exits non-zero on blocking issues even when JSON is printed.

### build-generation-scratchpad
- **When**: final execution contract before `generate`.
- **CLI**: `python3 mcp/brand_iterate.py build-generation-scratchpad --plan <draft.json> --format json`
- **MCP**: `brand_build_generation_scratchpad(plan="/abs/path/to/draft.json")`
- **Returns**: generation scratchpad payload with prompt context, refs, execution settings.
- **Gotcha**: use `--refresh-reference-analysis` only when refs changed; otherwise the cache is better.

### generate
- **When**: run from a scratchpad or let `pipeline` do it.
- **CLI**: `python3 mcp/brand_iterate.py generate --scratchpad <scratchpad.json>`
- **MCP**: `brand_generate(scratchpad="/abs/path/to/scratchpad.json")`
- **Returns**: version id, output files, manifest entry, review linkage.
- **Gotcha**: do not run parallel generations into the same workspace; version allocation races still exist.

### messaging loop
- **Ideate**: `python3 mcp/brand_iterate.py ideate-messaging --format json` / `brand_ideate_messaging()`
- **Persist**: `python3 mcp/brand_iterate.py update-messaging --tagline "..." --add-headline "..." --format json` / `brand_update_messaging(...)`
- **Material copy**: `python3 mcp/brand_iterate.py ideate-copy --material-type x-feed --goal "..." --format json` / `brand_ideate_copy(...)`
- **Promote**: `python3 mcp/brand_iterate.py promote-messaging --include-copy-notes` / `brand_promote_messaging(include_copy_notes=true)`
- **Returns**: `ideate-messaging` returns brand context plus instructions; the agent reads that context and generates **3–5 positioning angles** itself.
- **Gotcha**: image models should not invent key headlines; get them from conversation + messaging memory first.

### summary / memory inspection
- **Workspace summary**: `python3 mcp/brand_iterate.py show-session-summary --format json` / `brand_show_session_summary()`
- **Blackboard**: `python3 mcp/brand_iterate.py show-blackboard --format json` / `brand_show_blackboard()`
- **Manifest**: `python3 mcp/brand_iterate.py show --format json --latest 5` / `brand_show(format="json", latest=5)`
- **Compare board**: `python3 mcp/brand_iterate.py compare --all` / `brand_compare(all_versions=true)`
- **Iteration memory**: `python3 mcp/brand_iterate.py show-iteration-memory --format json` / `brand_show_iteration_memory()`
- **Gotcha**: `show-session-summary` is the fastest “what changed?” command; use the others only when you need raw detail. `compare --all` is the best visual history view and now includes copyable prompts for regenerating from any prior version.

### review-brand
- **When**: after generating something serious and before asking the user for a final score.
- **CLI**: `python3 mcp/brand_iterate.py review-brand --version v17`
- **MCP**: `brand_review(version="v17")`
- **Returns**: a review packet that includes critique lenses, severity buckets, and a **provisional suggested score + feedback command** the agent can show to the user for confirmation.
- **Gotcha**: treat the suggested score as a proposal, not saved truth. Persist it only after the user confirms or clearly implies the preference.

### diagnose
- **When**: a generation produced nonsense and you need to understand why.
- **CLI**: `python3 mcp/brand_iterate.py diagnose v14 v15 --format json`
- **Returns**: side-by-side comparison of prompt length, prelude length, raw prompt length, ref count, model, aspect ratio, prompt review status, critic issues, workflow_id, and scratchpad path.
- **Gotcha**: if `prompt_chars` is far above `raw_prompt_chars`, the prelude is bloated. Non-interface materials get the full mark anatomy + composition pattern guardrails, which can easily exceed model limits.

### brand management
- **List brands**: `python3 mcp/brand_iterate.py list-brands --format json` / `brand_list(format="json")`
- **Switch brand**: `python3 mcp/brand_iterate.py use <brand-key>` / `brand_use(brand="<key>")`
- **Init workspace**: `python3 mcp/brand_iterate.py init --brand-name "<name>"`
- **Create brand from conversation**: `python3 mcp/brand_iterate.py create-brand --name "<name>" --description "<what it is>" --tone "calm,technical" --palette "#1A6B6B,#C85A2A"` / `brand_create(name="<name>", description="...", tone=[...], palette=[...])`
- **Extract brand**: `python3 mcp/brand_iterate.py extract-brand --project-root <path> --brand-name "<name>"` / `brand_extract(project_root="<path>", brand_name="<name>")`
- **Start testing session**: `python3 mcp/brand_iterate.py start-testing --session-name "<name>" --brand <brand-key> --goal "<goal>"`
- **Gotcha**: `start-testing --brand <key>` seeds the session from the saved brand. Without `--brand`, the session starts as a fresh testing workspace.

### set workflows
- **CLI**: `plan-set --template <template> --format json` → `validate-set --set <set.json>` → `generate-set --set <set.json>`
- **MCP**: `brand_plan_set(...)`, `brand_validate_set(...)`, `brand_generate_set(...)`
- **Returns**: coordinated plan/set payloads and generated member outputs.
- **Gotcha**: sets are a separate path; do not expect `pipeline` to orchestrate a family of materials.

## Negative examples / don't do this

- Don't run `pipeline` with a prompt seed over roughly **400 chars** for interface materials. It may pass critique but still create a bloated resolved prompt that image models handle poorly. Run `review-prompt --format json` first if you're unsure.
- Don't send more than **2 refs** for interface materials unless you are debugging reference behavior. More refs usually create muddier compositions, not richer ones.
- Don't assume the saved brand identity is the active truth. Sessions often use a copied workspace; if messaging feels missing, inspect `show-session-summary` before editing the saved brand.
- Don't use `open`/folder-review flows as the primary agent loop when `--format json` is available.
- Don't use `start-testing` when the user actually wants a durable saved brand immediately; prefer `create-brand` for conversation-first onboarding.
- Don't assume `init --brand-name` is the best conversation-first path; it now scaffolds usable files, but `create-brand` is better because it captures description, tone, and palette in one step.

## Brand-specific material policies

Material defaults (product truth expressions, purposes, target surfaces) come from
`MATERIAL_BRAND_POLICIES` in source. To override these per-brand, add a
`material_policies` section to `brand-identity.json`:

```json
{
  "material_policies": {
    "browser_illustration": {
      "product_truth_expression": "a real Acme dashboard with the project timeline visible",
      "purpose": "package one real Acme moment inside a branded frame"
    },
    "social": {
      "product_truth_expression": "one Acme workflow screenshot or product claim"
    }
  }
}
```

These merge on top of the defaults so you only need to specify what differs.
If no `material_policies` section exists, the generic defaults apply.

## Load-on-demand references

Load `brand-gen-reference` only when you need:
- model selection guidance
- social/feed dimensions
- workspace file layout
- reference capture/source-selection details

## Rule

Prefer `pipeline` unless the user explicitly wants to inspect or change the intermediate artifacts. Keep semantic brand understanding (positioning, product truth, approved copy) ahead of visual prompting.
