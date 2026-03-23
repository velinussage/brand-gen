# Image Generation Workflow

<required_reading>
Before starting: verify setup with `workflows/setup.md` if first run.
Prompting tips: `references/prompting-guide.md`
</required_reading>

<process>

## 1. Choose Model

| Need | Model | Cost |
|------|-------|------|
| Best quality photorealism | flux-pro | $0.04 |
| Fast iteration / drafts | flux-schnell | $0.003 |
| Wide style range | sdxl | $0.008 |
| Logos, icons, vectors | recraft-v3 | $0.04 |

## 2. Write Prompt

Follow the master template: **Subject + Style + Lighting + Composition + Details**

**Good:** "Professional headshot of a woman with auburn hair, natural window lighting, shallow depth of field, 85mm lens, neutral gray background, warm color palette"

**Bad:** "photo of woman" (too vague — no style, lighting, or composition guidance)

### Use Presets for Common Cases

Add `--preset` to auto-wrap your prompt with quality modifiers:

- `portrait` — Studio lighting, shallow DoF, 85mm lens
- `product` — Clean white background, commercial quality
- `landscape` — Golden hour, wide angle, HDR
- `illustration` — Clean lines, vibrant colors
- `logo` — Minimalist vector, flat colors
- `ui-mockup` — Clean layout, consistent spacing
- `browser-product` — Real product screenshot packaged in refined browser framing
- `feed-card` — Social/feed-safe product composition with strong crop
- `artistic` — Fine art, masterful brushwork

### UI / Product Visuals

For browser illustrations, product banners, and social/feed visuals, read:
- `prompts/replicate/ui-design-guide.md`

Use this structure:

```text
Use the real product screenshot as the hero asset +
[surface type] +
[presentation context] +
[style words] +
[composition rule] +
Do not redesign the UI
```

Good:
- `Use the real product screenshot as the hero asset. Landing page screenshot in a browser window, minimalistic, flat design, clean UI, subtle light background, tighter crop on the strongest component, airy spacing. Do not redesign the UI.`
- `Use the real product screenshot as the hero asset. Feed view in a browser frame, 16:9 product marketing image, clean UI, stronger focal crop, safe margins, minimal or no overlays. Do not redesign the UI.`

Bad:
- `Beautiful futuristic SaaS dashboard`
- `Modern startup UI`
- `Minimal landing page design`

Those invite hallucinated redesigns instead of preserving the real product.

## 3. Generate

```bash
source ~/.claude/.env

# Standard generation
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-pro -p "YOUR PROMPT" -o output.webp

# With preset
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-pro -p "Woman with auburn hair" --preset portrait -o portrait.webp

# Custom dimensions
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-pro -p "YOUR PROMPT" --width 1440 --height 960 -o wide.webp

# With negative prompt
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m sdxl -p "YOUR PROMPT" -n "blurry, watermark, low quality" -o output.png

# With seed for reproducibility
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-pro -p "YOUR PROMPT" --seed 42 -o output.webp

# Image-to-image (reference image)
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m sdxl -p "Oil painting style" -i reference.jpg -o styled.png
```

## 4. Iterate

- **Quality too low** → switch to flux-pro
- **Style is wrong** → add more specific style descriptors
- **Composition off** → add camera angle, lens, framing details
- **Colors wrong** → specify color palette explicitly
- **Unwanted elements** → add negative prompt with `-n`
- **Same composition, new style** → use same `--seed` with modified prompt

</process>

<success_criteria>
- Output image file exists and opens correctly
- Subject matches prompt description
- Style and lighting match requested
- No artifacts, distortion, or unwanted elements
</success_criteria>

<anti_patterns>
- Don't use flux-schnell for final outputs (draft quality only)
- Don't omit lighting/style descriptors (results will be generic)
- Don't use contradictory style terms ("photorealistic watercolor")
- Don't set guidance_scale above 15 (causes artifacts on most models)
- Don't use tiny dimensions (below 512px causes quality issues)
</anti_patterns>
