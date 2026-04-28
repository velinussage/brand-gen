# Complex Workflow Recipes

Multi-step workflows that need more guidance than the main skill provides.

## Table of Contents

- [Live app capture → social card](#live-app-capture--social-card)
- [Base-image editing / overlays](#base-image-editing--overlays)
- [Carousel generation](#carousel-generation)
- [Card composition rules](#card-composition-rules)
- [When to capture vs. use inspiration](#when-to-capture-vs-use-inspiration)
- [Import canon from an external vault](#import-canon-from-an-external-vault)
- [Terminal / CLI material types](#terminal--cli-material-types)
- [Retiring the artifact / share-card flow for a brand](#retiring-the-artifact--share-card-flow-for-a-brand)

---

## Live app capture → social card

When a user wants a social card that shares **real product data** (a prompt, skill, feature page), use a **hybrid truth-first workflow**. Default to **raw screenshot + base-image editing** first. Deterministic composition is a fallback for extreme text-integrity cases, not the default.

### Decision: capture vs. inspiration

Use **live app captures** when:
- the card should show real names, statuses, copy, metadata, or UI structure
- the user wants to share a specific prompt, skill, library, or page from the product
- the asset should read as **proof** ("this exists now"), not concept art
- previous generations garbled or abstracted the text

Use **inspiration refs** when:
- the material needs better taste, pacing, or composition
- the product truth is already covered by a screenshot but the framing feels flat
- you need help with hierarchy, crop discipline, whitespace, or surface attitude

### Recipe

1. **Capture the live detail page**

```bash
python3 scripts/product_screens.py capture \
  --session live-share-capture \
  --shot skill-detail=https://app.example.com/skills/skill-detail \
  --out-dir /abs/path/to/brand-materials/product-screens-live
```

Capture the **specific detail page**, not a generic overview. A prompt/skill detail page is better than a feed screenshot.

2. **Default path: edit the raw screenshot into a branded state card**

```bash
bgen pipeline \
  --material-type state-card \
  --base-image /abs/path/to/product-screens-live/skill-detail-01.png \
  --pick product_truth=/abs/path/to/product-screens-live/skill-detail-01.png \
  --pick motif=/abs/path/to/brand/logo.png \
  --prompt-seed "Turn this real product screenshot into a premium square state-share card. Preserve the visible page title, UI labels, and product structure. Reframe it into one bounded carrier with a subtle illustrated background field and stronger editorial crop. No invented text and no decorative overlays on top of the UI." \
  --format json
```

Prefer this for prompt/skill detail pages. It keeps the output more aesthetic than a deterministic card while still anchoring on real product truth.

3. **Fallback only when exact text integrity keeps drifting: use the official HTML share-card path**

```bash
bgen pipeline \
  --material-type announcement-card \
  --render-backend html \
  --source-url "https://app.example.com/skills/skill-detail" \
  --entity-type skill \
  --proof-meta "Live product detail" \
  --proof-row "Structured, source-derived share card" \
  --format json
```

This is the public deterministic route. It derives structured share-card content from the source URL and renders it through the HTML card engine instead of relying on a private host script.

4. **Optional advanced local path: compose a screenshot-backed carrier yourself**

If you already have the screenshot and want a manual carrier image before any polish step, the repo still ships a utility script:

```bash
python3 scripts/compose_live_share_card.py \
  --screenshot /abs/path/to/product-screens-live/skill-detail-01.png \
  --title "browser-automation-skill" \
  --subtitle "Headless browser automation for agents" \
  --community "Example Community" \
  --eyebrow "New skill" \
  --badge "Skill" \
  --screenshot-label "Live app detail" \
  --logo /abs/path/to/brand/logo.png \
  --output /abs/path/to/live-social-cards/skill-share-base.png
```

Use this only when you explicitly need a screenshot-backed base image that you control by hand.

5. **Optional: polish the deterministic carrier with Flux (don't redraw the truth)**

```bash
bgen pipeline \
  --material-type social \
  --base-image /abs/path/to/live-social-cards/skill-share-base.png \
  --image /abs/path/to/brand/logo.png \
  --prompt-seed "Polish this existing square social card carrier only. Keep the screenshot inset, title, subtitle, metadata pill, and card geometry intact. Do not redraw the product UI. Do not rewrite any visible text. Keep every element fully inside the rounded card. Improve the brand carrier with a quieter premium background field, subtle texture, cleaner spacing, and more editorial finish." \
  --format json
```

Use this only if the raw-screenshot state-card path still fails and the user prefers truth over taste.

6. **If needed, normalize to platform size**

Some edit models return a model-native size (e.g., `1008x1008`) even when the base was `1200x1200`. Resize after the edit pass:

```python
from PIL import Image
Image.open("polished.png").resize((1200, 1200), Image.Resampling.LANCZOS).save("final.png")
```

### Composition pattern

The strongest pattern for live data cards:
- one branded outer card
- one real product truth surface
- one bounded carrier around that surface
- optional short deterministic title/subtitle only when the screenshot alone is not enough
- one or two quiet metadata pills
- no extra floating UI fragments outside the card

Ban elements that bleed past the card edge, float outside the frame, or cross the border. Prefer one inset maximum and one clear title block.

---

## Base-image editing / overlays

When the user has an existing image and wants branded overlays, text, icons, or edits on top of it.

```bash
bgen pipeline \
  --material-type podcast-cover \
  --base-image /path/to/photo.jpg \
  --image /path/to/brand-mark.png \
  --prompt-seed "Add title bar with 'Intro to X' and pillar mark icon in bottom-left" \
  --format json
```

**What happens**: auto-selects `flux-2-pro`. The base image is the primary input; brand reference assets are additional references. The prompt instructs the model what to add/overlay.

**Prompt style**: use instruction language ("Add X to Y", "Place Z in bottom-left"), not descriptive language ("A poster with X and Y"). The model edits the existing image rather than generating from scratch.

**Extra references**: pass stored brand assets via `--image` alongside `--base-image` — e.g., the pillar mark PNG so the model knows exactly what icon to place.

---

## Carousel generation

For multi-slide carousels, generate each slide separately with the content brief:

```bash
# Plan the content brief first (or use brand-content-ideation skill)
bgen ideate-copy --material-type carousel-slide --goal "..." --format json

# Generate each slide
bgen pipeline --material-type carousel-slide \
  --prompt-seed "Slide 1/6 — Hook. Headline: 'Your AI agent has more power than most employees.' Subhead: 'But zero accountability.' Visual: typography-only, bold display font on brand background." \
  --mode hybrid --format json
```

### Carousel narrative arc

| Slide | Role | Design treatment |
|-------|------|-----------------|
| 1 | Hook | One oversized headline, minimal text, high contrast |
| 2 | Empathy | Validate the pain point, 2-3 sentences |
| 3-6 | Value | Key info, one point per slide |
| 7 | Proof | Stats, testimonials, or case study |
| 8 | CTA | Clear call-to-action + brand mark |

### Platform dimensions

| Platform | Ratio | Resolution | Max slides |
|----------|-------|-----------|------------|
| Instagram | 4:5 | 1080x1350 | 20 |
| LinkedIn | 4:5 or 1:1 | 1080x1350 or 1080x1080 | 10-12 |
| X/Twitter | 16:9 or 1:1 | 1600x900 or 1080x1080 | 4 |

Run `bgen social-specs` for live platform dimensions.

---

## Card composition rules

### Explicit card bounds

For card-style generations, protect the card bounds in the prompt:
- the screenshot/inset must sit **fully inside one rounded card**
- ban elements that bleed past the card edge, float outside the frame, or cross the border
- prefer one inset maximum and one clear title block
- if repeated generations leak content outside the card, switch to base-image editing or deterministic composition

### Typography hierarchy for content cards

- **Headline**: 36pt+ display font, can be 48-72pt for hook slides
- **Subhead**: 24-28pt, accent color or bold weight
- **Body text**: 22-24pt minimum, regular weight
- **CTA text**: 20-24pt, with arrow marker

### Card archetypes

1. **Typography-only**: Headline dominates, body below, brand mark anchored
2. **Text + photo inset**: Text fills 70%, rounded photo circle in corner
3. **Text + illustration**: Branded illustration top, text block below
4. **List card**: Subhead + bullet list, clean whitespace
5. **Stat highlight**: One big number + context sentence

---

## When to capture vs. use inspiration

| Signal | Use live app capture | Use inspiration refs |
|--------|---------------------|---------------------|
| Card should show real product data | Yes | No |
| Previous generations garbled text | Yes | No |
| Asset should read as "proof" | Yes | No |
| Need better taste/composition | No | Yes |
| Product truth already covered by screenshot | No | Yes |
| Need help with hierarchy or whitespace | No | Yes |

Best default for product-sharing social cards:
1. Capture **one targeted live product screenshot** (prefer detail pages over generic feeds)
2. Pass as `--pick product_truth=/abs/path/to/capture.png`
3. Add **one** application/composition inspiration ref for polish
4. Keep copy deterministic and short

If the user needs exact live app data preserved and image generations keep abstracting it, prefer a deterministic composed card over another freeform image-model pass.

---

## Import canon from an external vault

Use this when the brand's truth lives outside the repo — an Obsidian vault, a docs monorepo, a sibling canon repo — and you want brand-gen to absorb it without duplicating files.

### When to reach for it

- a brand's approved messaging / forbidden claims / voice direction live in a markdown canon that other teams already maintain
- product truth (screenshots, terminal recordings, UI chrome) updates in a repo you don't own
- you want a **per-brand** fat skill that points at that canon instead of flattening it into `brand-profile.json`

### Recipe

1. **Point `BRAND_SOURCE_VAULT` at the canon directory**

   ```bash
   export BRAND_SOURCE_VAULT="$HOME/Dev/<their-canon-repo>/compiled"
   ```

   Pi agents: set `vault_paths` inside `.brand-gen-local.json` instead. Both mechanisms feed the same inspiration-doctrine loader.

2. **Extract inspiration from the vault**

   ```bash
   bgen extract-inspiration --category messaging
   bgen extract-inspiration --category symbol
   bgen consolidate-inspiration --format json
   bgen inspiration-mode on
   ```

3. **Seed a `messaging_canon` block on the brand identity**

   The generic `messaging` schema accepts two claim lists any brand can use:

   ```json
   {
     "messaging": {
       "tagline": "...",
       "elevator": "...",
       "voice": { "description": "..." },
       "approved_claims": [
         "Bounded claim 1 that matches current reality",
         "Bounded claim 2 that's safe to repeat in copy"
       ],
       "forbidden_claims": [
         "phrase the critic should block",
         "another phrase that overclaims"
       ]
     }
   }
   ```

   `approved_claims` surface as subheadline candidates inside `bgen ideate-copy`. `forbidden_claims` are substring-checked during `critique-plan` and `build-generation-scratchpad` — a match becomes a blocking issue before generation.

4. **Register any external assets (screenshots, recordings) as typed references**

   Copy (don't symlink) evidence into `brands/<brand>/references/` so reference analysis sees a stable path. Keep one role per file:

   ```
   brands/<brand>/references/
     <brand>-product-anchor.png
     <brand>-cli-anchor.png
     <brand>-voice-anchor.md
   ```

5. **Author a per-brand local skill file**

   Keep brand-specific context in `brands/<brand>/SKILL.local.md` or `skills/brand-gen/SKILL.local.md` additions. Brand-gen core stays generic; the per-brand fat skill points at the canon, names the reference manifest, and lists the refresh recipe. Do not bake brand-specific canon into `data/*.json`.

6. **Smoke the loop**

   ```bash
   bgen use <brand>
   bgen pipeline --material-type <material> --mode hybrid --format json
   ```

   Watch the critique output for forbidden-claim blocks and warnings about missing references.

### Rule

Generic support lives in brand-gen. Brand-specific canon lives with the brand. A recipe in this file should work for any brand that maintains canon outside the repo — not just the first one that motivated it.

---

## Terminal / CLI material types

`terminal-hero`, `cli-recording`, and `command-illustration` are for brands whose product is a command-line tool. Treat the terminal text as documentary truth — the same way product screenshots are treated elsewhere.

### When each fits

| Material | Surface | Fit |
|---|---|---|
| `terminal-hero` | docs hero, launch page | one complete CLI moment framed for size |
| `cli-recording` | social launch, changelog | a single frame pulled from a real recording |
| `command-illustration` | docs section, carousel | command + explanatory branded diagram |

### Rules

- the prompt, command, and output must stay verbatim — never let the image model rewrite shell text
- capture a real frame first (VHS `.tape`, `asciinema`, or a manual screenshot) and pass it with `--image` or `--base-image`
- keep the carrier quiet: one brand field, one mark anchor, no invented syntax highlighting or neon trails
- `--render-backend native` by default; use `--render-backend html` only when you need pixel-perfect shell output

### Example

```bash
bgen pipeline \
  --material-type terminal-hero \
  --mode hybrid \
  --base-image /abs/path/to/terminal-recording-frame.png \
  --prompt-seed "Real CLI moment framed as a docs hero: preserve the prompt, command, and output verbatim; compose a quiet brand field around it with the stored mark anchored at one junction. No invented syntax colors." \
  --format json
```

If the recording file is a `.gif` or `.mp4`, export one frame to PNG first — the pipeline expects still images for reference analysis.

---

## Retiring the artifact / share-card flow for a brand

The HTML share-card flow (`--render-backend html`, `--source-url`, `--proof-title`, `--proof-excerpt`, `--proof-row`, `--proof-crop-path`, `--skip-proof`, `--dark-mode`, `--layout-spec`) produces deterministic proof cards that show a headline plus a product-truth module plus an optional screenshot crop. For some brands this is the right move (launch announcements where the data is the story, doc heroes where the command is the story).

For other brands it is the wrong move: it can box the brand into a templated card product instead of a brand. Symptoms include:

- the screenshot / proof inset never actually earns its place in the composition
- trust reads as UI chrome rather than as tone, typography, restraint, and composition
- the brand starts to feel like "branded tweet cards" instead of a recognizable visual system
- the pattern system and mark get relegated to decoration around a central "artifact" frame

When a brand hits this point, retire the artifact flow for that brand without removing the code path for other brands. The mechanism:

### 1. Mark the patterns as forbidden in the brand's custom scratchpad

Add these to `.brand-gen/brands/<brand>/custom-scratchpad.json` via `append_forbidden_pattern` or by editing directly:

- `floating proof panel`
- `screenshot inset next to headline`
- `card within card`
- `source url display`
- `prompt details text`
- `proof module UI`
- `real product crop as trust device`
- `share-card chrome`
- `artifact-UI mimicry`

The pipeline auto-injects these into every prompt prelude and also auto-lists them in the critic's ban pass.

### 2. Pin the brand to native generation (not HTML)

In the same `custom-scratchpad.json`, set `model_overrides_by_material` for the brand's copy-bearing materials to a native model:

```json
"model_overrides_by_material": {
  "x-feed": {"model": "nano-banana-2", "mode": "reference"},
  "linkedin-card": {"model": "nano-banana-2", "mode": "reference"},
  "social": {"model": "nano-banana-2", "mode": "reference"},
  "announcement-card": {"model": "nano-banana-2", "mode": "reference"}
}
```

The orchestrator's Phase 1 step 4b reads these before any learnings lookup, so the override fires automatically without a CLI flag.

### 3. Write the new direction into `custom-scratchpad.md`

State the working rule explicitly so the philosopher and planner have it in the prompt prelude:

```markdown
## Working rule

Retire the artifact/share-card flow for this brand. Trust comes from tone,
typography, restraint, and composition — not from a floating UI panel
proving "this is a real product". If we show product later, it is
intentional product art direction, not an inset screenshot.
```

And list the approved directions the brand does lean into, for example:

- Typographic statement poster (headline + pattern atmosphere)
- Pattern-led social composition (large crop of the brand pattern system)
- Symbol + field (mark used once, pattern carries the rest)
- Editorial brand frame without artifact UI (structured grid, no card-within-card)

### 4. Leave the HTML share-card code alone

The `brand_gen/html_share_cards.py` module, the `--render-backend html` flag, and all proof/share-card CLI arguments stay in place. Other brands may still use them. What changed is the brand's scratchpad, not brand-gen itself.

### 5. Revalidate prior assumptions in iteration memory

If the brand previously had winning scores on share-card outputs, those still count as positive examples for their specific composition, but the brand is no longer pursuing that direction. Optionally move those entries to a `legacy_positive_examples` bucket or append a note: "approved at the time under the artifact flow; flow retired YYYY-MM-DD — do not derive new work from these anchors".

### When to revisit

Re-open the artifact flow for the brand only when:

- the brand needs a genuinely data-forward deliverable (launch announcement with concrete stats, changelog hero)
- the user explicitly asks for an artifact/share-card treatment
- a test pass shows the pattern-led or typographic directions cannot carry the specific message

In all other cases, the retirement holds.

---

## DSPy-scored critique (v2 rubric)

Use when you want structured axis scores + rationales pre-populated before the critic reviews, or when a critic agent is running headless and needs machine-readable evidence.

### 1. One-time install

```bash
pip install -e '.[scoring]'
echo "OPENROUTER_API_KEY=sk-or-v1-..." >> .env   # .env is gitignored
```

Default judge LM is `openrouter/anthropic/claude-haiku-4.5` (~$0.003 per critique with prompt caching). Override with `BRAND_GEN_SCORER_MODEL` or `--scorer-model` when cost-modeling.

### 2. Score a generated version

```bash
bgen critique-rubric v12 --dspy-scorer --format json
```

The v2 packet includes:

- `axis_scores` — universal 6 + material overlay axes (`value_proposition_fidelity`, `surface_fit`, `system_logic_visible`, etc.)
- `axis_rationales` — 1-2 sentence explanation per axis
- `overall_score` — min-biased aggregation
- `decision` — `approve` / `iterate` / `reject`
- `disqualifier_triggered` + `disqualifier_rule` — auto-fail guard per material
- `why_user_might_dislike_if_polished` — the honest failure signal in plain language
- `scorer_version`, `rubric_version` — for reproducibility

### 3. Inspect the contract before scoring

```bash
bgen show-rubric --material-type concept-illustration --format json
```

Returns axis definitions + overlay axes + disqualifier rule. Use this when planning to see the scoring target explicitly.

### 4. Audit agent vs user agreement

When a user score diverges from the agent score by ≥2, the delta auto-logs to `<brand-dir>/scoring/disagreements.jsonl`. Inspect:

```bash
bgen show-disagreements --bucket calibration_failure --limit 20 --format json
bgen scoring-status --format json
```

`scoring-status` returns bucket counts, partition split (`holdout_a` / `holdout_b`), weighted Cohen's kappa (quadratic weights), and raw agreement rate when enough records exist.

### 5. Override the judge model

```bash
bgen critique-rubric v12 \
  --dspy-scorer \
  --scorer-model openrouter/anthropic/claude-sonnet-4.5 \
  --format json
```

Use Sonnet 4.5 when Haiku plateaus on calibration (rising `calibration_failure` bucket in scoring-status). Reserve Opus-class models for the reflection LM in v2 GEPA, not for routine scoring.

### Notes

- The scorer bypasses DSPy Signature formatting for the per-axis calls and builds OpenAI-compatible messages inline so Anthropic `cache_control` breakpoints survive through LiteLLM and OpenRouter. Expect ~75% cost reduction after the first call in a critique batch from prompt-cache hits.
- All three critic-agent files (`.claude/agents/`, `.pi/agents/`, `skills/brand-gen/claude-agents/`) embed the rubric markdown verbatim via `rubric_registry.to_markdown()`. When axes change in `brand_gen/scoring/rubric_registry.py`, regenerate with:
  ```bash
  python3 -c "
  from brand_gen.scoring import to_markdown
  import re
  canonical = to_markdown().strip()
  for path in ['.claude/agents/brand-critic.md', '.pi/agents/brand-critic.md', 'skills/brand-gen/claude-agents/brand-critic.md']:
      content = open(path).read()
      new = re.sub(
          r'(<!-- BEGIN rubric_registry\.to_markdown\(\).*?-->)(.*?)(<!-- END rubric_registry\.to_markdown\(\) -->)',
          lambda m: f'{m.group(1)}\n\n{canonical}\n\n{m.group(3)}',
          content, flags=re.DOTALL,
      )
      open(path, 'w').write(new)
  "
  ```
