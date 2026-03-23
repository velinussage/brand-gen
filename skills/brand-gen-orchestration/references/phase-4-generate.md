# Phase 4: Generate

## Table of Contents

1. [Build the Scratchpad](#build-the-scratchpad)
2. [Scratchpad Flags Reference](#scratchpad-flags-reference)
3. [Handle Blocking Issues](#handle-blocking-issues)
4. [Run Generation](#run-generation)
5. [Interface Material Generation](#interface-material-generation)
6. [Generation Output](#generation-output)
7. [Iteration via Pipeline](#iteration-via-pipeline)

---

## Build the Scratchpad

**Why:** The scratchpad is the final, resolved generation config — it takes the
validated plan and resolves all references, paths, brand assets, and model parameters
into a single self-contained JSON. This separation means plans are portable and
scratchpads are executable.

```bash
source .venv/bin/activate && bgen build-generation-scratchpad \
  --plan <plan-path> \
  --format json
```

The scratchpad auto-injects:
- Brand logo via `resolve_brand_asset_paths()`
- Color palette from brand identity
- Brand guardrail prelude
- Resolved reference image paths

Read the returned scratchpad path. Verify the scratchpad JSON is well-formed before
proceeding.

Before generation, compare the final execution prompt/scratchpad against the approved plan.
If key planned mechanics disappeared during prompt assembly (for example: explicit panel borders,
required prior-winner mechanics, or the intended brand-mark preservation strategy), stop and revise
instead of “seeing what the model does.”

---

## Scratchpad Flags Reference

Most flags mirror `plan-draft` because the scratchpad builder can also receive
overrides. Common overrides:

| Flag | When to use |
|------|------------|
| `--base-image <path>` | Interface materials — MANDATORY |
| `--skip-extraction` | Skip re-extracting references (use cached) |
| `--refresh-reference-analysis` | Force re-analysis of references |
| `--critique-mode advisory` | Relaxed critique (default) |
| `--critique-mode strict` | Strict critique for brand-critical materials |
| `--allow-blocking` | Override blocking issues (use with caution) |
| `--render-backend html` | Use HTML/Chromium rendering instead of native |
| `--layout-spec <json>` | Override layout with specific JSON spec |
| `--headline <text>` | Override headline text |
| `--subhead <text>` | Override subhead text |
| `--cta <text>` | Override CTA text |

For proof-of-content style materials (announcement cards, blog post previews):

| Flag | Purpose |
|------|---------|
| `--source-url <url>` | URL of the content being promoted |
| `--entity-type <type>` | Type of entity (blog_post, announcement, etc.) |
| `--proof-title <text>` | Title to display |
| `--proof-excerpt <text>` | Excerpt to display |
| `--proof-row <text>` | Metadata row text |
| `--proof-meta <text>` | Additional metadata |
| `--proof-crop-path <path>` | Cropped image for proof display |

---

## Handle Blocking Issues

**Why:** The scratchpad builder runs its own validation pass. If it finds issues the
plan critique missed (usually because of reference resolution failures), it blocks
generation. Generating from a broken scratchpad wastes money and produces garbage.

If the scratchpad output contains blocking issues:

1. Read the blocking reasons
2. Determine if the issues are:
   - **Reference failures** — a source image path does not exist or is corrupt
   - **Parameter conflicts** — incompatible flags after resolution
   - **Brand asset missing** — logo or required brand mark not found
3. Fix the root cause:
   - For missing references: check paths, re-capture if needed
   - For parameter conflicts: return to Phase 2 and adjust the plan
   - For missing brand assets: resolve via logo resolution (Phase 1 step 11)
4. Rebuild the scratchpad

Do not use `--allow-blocking` unless you have explicitly verified the blocking issue
is a false positive.

---

## Run Generation

```bash
source .venv/bin/activate && bgen generate \
  --scratchpad <scratchpad-path> \
  --max-iterations 2
```

### What `--max-iterations` Does

The `--max-iterations` flag controls the internal VLM (vision-language model) critique
loop within a single generation call:

- `1` — Generate once, no self-critique. Fastest but no quality loop.
- `2` — Generate, self-critique, regenerate if the VLM finds issues. Default.
- `3` — Up to 3 internal cycles. Use for critical, high-stakes materials.

The default of 2 balances quality with cost. Each iteration costs one generation API
call plus one VLM critique call.

### Generation Process

1. The generator reads the scratchpad
2. Resolves the final prompt (brand guardrails + prompt seed + model-specific formatting)
3. Calls the image generation API
4. If `max-iterations > 1`, runs a VLM critique on the result
5. If the VLM finds issues, regenerates with adjustments
6. Saves all outputs to the manifest with version IDs

---

## Interface Material Generation

For `browser-illustration`, `landing-hero`, `product-banner`, `feature-illustration`:

1. ALWAYS pass `--base-image <screenshot-path>` to `build-generation-scratchpad`
2. Verify the scratchpad output contains a non-empty `base_image` field
3. If `base_image` is empty or missing, stop — the screenshot was not resolved
4. Without a real screenshot, the image model invents fake UI that:
   - Has nonsensical menu items
   - Shows random chart data
   - Contains garbled text labels
   - Scores 1-2/5 on material_truth every time

This is not a soft recommendation. It is a hard requirement.

---

## Generation Output

After generation, read the result. It includes:

- **version_id** — The new version identifier (e.g., `v048`)
- **image_paths** — Absolute paths to generated image files
- **iterations** — How many internal VLM loops ran
- **all_versions** — If multiple iterations, all version IDs created
- **generation_metadata** — Model used, workflow ID, material type

Inspect the image at the returned path. This is what Phase 5 will critique.

If multiple iterations occurred, note what changed between them — this information
helps Phase 5 understand what the VLM already tried to fix.

---

## Iteration via Pipeline

When Phase 5 returns ITERATE (score < 3), use the pipeline command for iteration
rather than rebuilding manually:

```bash
source .venv/bin/activate && bgen pipeline \
  --material-type <type> \
  --source-version <version-to-iterate-from> \
  --ban "<specific defect from critique>" \
  --push "<specific improvement from critique>" \
  --max-iterations 2 \
  --format json
```

The `--source-version` flag tells the pipeline to iterate from a specific previous
version, carrying forward what worked and addressing what did not.

Key iteration flags:
- `--ban` (repeatable) — Prohibit specific defects found in critique
- `--push` (repeatable) — Amplify specific qualities to improve
- `--preserve` (repeatable) — Keep elements that scored well
- `--max-retries 0-2` — Control how many times the pipeline internally retries

Maximum 2 retry cycles from Phase 5. If still below the bar, report honestly.
