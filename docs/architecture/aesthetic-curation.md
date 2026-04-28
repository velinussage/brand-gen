# Aesthetic curation architecture

Brand-gen now treats visual style as a curated, learnable input instead of a pile of first-principles adjectives. The goal is to let users say a useful shorthand like “Ghibli aesthetic” or “screenprinted poster,” while the runtime compiles that into safe, concrete art-direction terms that do not ask a model to copy a protected studio, artist, or exact work.

## Why this exists

The previous prompt path over-described from first principles (`warm`, `editorial`, `premium`, `AI`, etc.). In practice, image models often respond better to compact style handles and/or visual references, then need concrete constraints to preserve the brand.

Current prompting and design tooling patterns support this direction:

- Midjourney moodboards use curated images to express a wider aesthetic range when words are not enough, and allow multiple distinct moodboards by project/style. Source: <https://docs.midjourney.com/hc/en-us/articles/39193335040013-Moodboards>
- Adobe Firefly separates style reference from the text prompt and exposes a strength control, reinforcing that “look and feel” should be an explicit input rather than buried in prose. Source: <https://developer.adobe.com/firefly-services/docs/firefly-api/guides/concepts/style-image-reference/>
- Brand-board workflows converge from exploratory moodboards into explicit decisions: color, typography, logo variations, icon/pattern styles, and real applications. Source: <https://miro.com/moodboard/mood-board-vs-brand-board-vs-style-guide/>
- Moodboard templates typically carry a central theme statement, imagery/photography style, color story, typography pairing, and patterns/UI elements — the same fields brand-gen compiles into prompt blocks. Source: <https://miro.com/templates/mood-board/>
- Prompt instructions should be specific, put important constraints up front, and use explicit format/structure when reliability matters. Source: <https://help.openai.com/en/articles/6654000-prompt-engineering-guide>

## Concepts

### Aesthetic capsule

A reusable art-direction/moodboard packet stored in `data/aesthetic_capsules.json`.

Each capsule includes:

- `id`, `label`, `safe_handle`
- `internal_handles` for user shorthand matching only
- `material_types` where the capsule is a reasonable default
- `use_when` / `avoid_when`
- `style_strength_default`
- `style_description` fields: `medium`, `palette`, `line`, `lighting`, `composition`, `density`, `texture`, `motifs`
- `positive_prompt_terms` and `negative_prompt_terms`

The safe prompt never prints protected shorthand from `internal_handles`; it prints the `safe_handle` plus descriptive fields.

### Aesthetic preferences

A brand-local learning file at:

```text
<brand-dir>/aesthetic-preferences.json
```

It stores:

- `selected_by_material` — persistent capsule choice by material type
- `preferred_capsules` / `negative_capsules`
- `style_likes` / `style_dislikes` with notes

Use this to make a new brand learn its own style without hard-coding Sage-specific prompts.

### Aesthetic archetype vs capsule

These are intentionally separate:

- `aesthetic_archetype` = composition paradigm for a material, such as a proof poster or paperback-like surface.
- `aesthetic_capsule` = art direction / moodboard language, such as warm editorial system illustration or screenprinted proof poster.

Prompt assembly injects the capsule before the archetype so the model gets the look-and-feel first, then the material-specific composition contract.


## External agent patterns folded in

A quick web / `gh skill search` pass found several recurring patterns worth adopting:

- Image-generation skills separate reference images by job: style transfer, subject consistency, composition guidance, and multi-reference combination. Brand-gen mirrors this with `reference_roles` on each capsule (`style`, `composition`, `brand`, `negative`).
- Template-based image agents keep per-template style guides, domain-knowledge rules, active style references, and provider fallback separate. Brand-gen mirrors this with global capsule data plus brand-local `aesthetic-preferences.json` instead of hard-coding Sage-specific taste.
- Visual-reference frontend agents run moodboard exploration before code/artifact execution: create 2-3 distinct branches, vary only one or two axes, choose one, then proceed single-line. Brand-gen mirrors this with `bgen suggest-aesthetic-directions` and `plan.aesthetic_direction_brief`.
- Img2img/style-transfer skills expose a strength control. Brand-gen stores `style_strength_default` plus each capsule's safe range in `iteration_policy`; prompt assembly tells the model to keep brand/product truth stronger than style transfer.
- Iterative image skills use an accept/regenerate/edit decision tree and add negative guidance after failures. Brand-gen maps this to review/evolve: style failures should call `promote-aesthetic-learning --sentiment dislike` or add a typed forbidden pattern, not merely append longer prompt prose.

## Runtime flow

1. Agent/user provides one of:
   - `--aesthetic-capsule <id>` for an explicit capsule, or
   - `--style-handle "..."` for shorthand, or
   - no style input, letting material/default/brand preferences select.
2. `brand_gen.aesthetic_curation.select_aesthetic_capsule()` scores candidates by:
   - material compatibility
   - explicit request
   - brand preference/dislike memory
   - style-handle/internal-handle match
3. The selected capsule is embedded into the plan as:
   - `aesthetic_capsule`
   - `aesthetic_capsule_id`
   - `aesthetic_capsule_selection`
4. `build-generation-scratchpad` renders `aesthetic_capsule_block` into the execution prompt via `render_capsule_prompt()`.
5. After user feedback, record durable preference with:

```bash
bgen promote-aesthetic-learning \
  --capsule-id screenprinted-proof-poster \
  --material-type social \
  --sentiment like \
  --note "Feels closer to the brand than generic gradients" \
  --format json
```

## CLI and typed-tool usage

List available capsules:

```bash
bgen list-aesthetic-capsules --material-type social --format json
```

Plan with a user shorthand:

```bash
bgen plan-run \
  --material-type system-explainer-illustration \
  --mode hybrid \
  --style-handle "storybook animation warmth" \
  --purpose "explain the product truth" \
  --target-surface social \
  --format json
```

Plan with an explicit curated capsule:

```bash
bgen plan-run \
  --material-type proof-poster \
  --aesthetic-capsule screenprinted-proof-poster \
  --purpose "show one real proof moment" \
  --target-surface social \
  --format json
```

Pi/host adapters should pass `style_handle` or `aesthetic_capsule` to `brand_orchestrate_material` or `brand_plan_run` when the user names a look.

## Prompt-safety rules

- Do not emit “copy Studio/Artist X” as execution prompt text.
- Use named references only as internal matching handles, then compile to `safe_handle` + concrete descriptors.
- Favor medium/palette/line/lighting/composition/density/texture over vague taste words.
- Pair positives with negatives. The negative list is where brand-gen bans generic failures like “floating orbs,” “DAO governance theater,” or “fake UI chrome.”
- Keep exact visible text on deterministic render paths (`html`, SVG, composite, typographic overlay). Aesthetic capsules are not a text-rendering fix.


## Additional aesthetic families for material prompts

A follow-up 2026 design-trend scan expanded the capsule library beyond the first proof/social set:

- **Structural neo-brutalist blueprint** — for product logic, data/process cards, terminal/proof surfaces, and hero modules that need transparent structure without generic gradients.
- **Tactile human collage** — for campaign/editorial materials that should counter AI hyper-polish with controlled human-made texture.
- **Friendly line-flat wayfinding** — for product education, icon/sticker families, and accessible small-screen illustration.
- **Kinetic typography campaign** — for announcement, event, podcast, poster, social, and motion materials where the headline/final hold is the hero.
- **Animated infographic data story** — for data/state/process cards and explainer motion where one metric or state change carries the story.
- **Heritage bold-minimal packaging** — for posters, merch, podcast covers, badges, and lockups that need distance-readable brand recognition.
- **Soft dimensional product object** — for hero/product visuals that need one tangible metaphor without sliding into generic 3D blobs.
- **Controlled retro-computing interface** — for terminal/CLI/developer nostalgia where command readability stays stronger than retro effects.

Research cues used: 2026 trend reports repeatedly emphasize human/tactile warmth over AI hyper-polish, restrained structural/brutalist/editorial grids, clean line-and-flat illustration for legibility, kinetic typography and motion as brand behavior, data storytelling/animated infographics, and logo/identity systems that derive details from brand story rather than generic effects. Sources: Creative Bloq graphic/illustration/logo/typography trend coverage, Graphic Design Junction 2026 trends, Digital Silk kinetic typography guidance, Lummi animation trends, Designity 2D animation trends, and current GitHub skill-search patterns for moodboard/style-reference agents.

## Adding a new capsule

1. Add an entry to `data/aesthetic_capsules.json`.
2. Keep `id` stable and lowercase-kebab-case.
3. Put user shorthand in `internal_handles`, but keep `safe_handle` descriptive and non-infringing.
4. Add material types where the capsule should be eligible.
5. Include at least five positive prompt terms and five negative prompt terms.
6. Run:

```bash
python -m pytest tests/test_aesthetic_curation.py -q
```

## Feedback loop

When a user scores a version low for style, record the capsule as disliked for that material instead of only adding another freeform ban. When a user likes a direction, promote the capsule for that material. Over time this gives each brand a curated aesthetic palette generated from feedback rather than Sage-specific defaults.
