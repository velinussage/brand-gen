---
name: imagevideogen
description: >
  Generate images and videos using multiple AI models via Replicate.
  Supports text-to-image (flux-pro, flux-schnell, sdxl, recraft-v3),
  text-to-video and image-to-video (kling, minimax, luma, veo),
  with built-in prompting best practices and presets.
  Trigger: generate image, generate video, create image, create video,
  text to image, text to video, image to video, t2i, t2v, i2v,
  imagevideogen, image gen, video gen, make an image, make a video,
  logo, icon, logo design, brand mark, logo generation, logo inspiration
tags: [image, video, generation, replicate, ai, creative, flux, kling, veo, logo, icon, brand]
mcp_servers: []
---

<overview>
Multi-model image and video generation skill using Replicate API.

**Image models:** flux-pro (photorealism), flux-schnell (fast/cheap), sdxl (versatile), recraft-v3 (vector/logos)
**Video models:** kling (portraits), minimax (atmospheric), luma (physics-aware), veo (cinematic+audio)

All generation runs through a single `generate.py` script with zero external dependencies.
Prompting presets and best practices are built in.

For UI/product visuals, use the screenshot-derived prompt rules in:
- `prompts/replicate/ui-design-guide.md`

Key rule:
- the real product screenshot is the **hero asset**
- style references only control framing and polish
- do **not** redesign the UI unless explicitly requested
</overview>

<check_setup>
Verify REPLICATE_API_TOKEN is available:

```bash
source ~/.claude/.env 2>/dev/null
if [ -z "$REPLICATE_API_TOKEN" ]; then
  echo "MISSING: Add REPLICATE_API_TOKEN to ~/.claude/.env"
else
  echo "OK: Token found (${REPLICATE_API_TOKEN:0:8}...)"
fi
```

If missing, get a token at https://replicate.com/account/api-tokens and add to `~/.claude/.env`:
```
REPLICATE_API_TOKEN=r8_your_token_here
```
</check_setup>

<intake>
What would you like to create?

1. **Generate an image** — Text-to-image with model selection
2. **Generate a video** — Text-to-video from a description
3. **Animate an image** — Image-to-video (provide a source image)
4. **Design a logo/icon** — Logo generation with recraft-v3 + inspiration browsing
5. **Quick draft image** — Fast cheap image with flux-schnell ($0.003)
6. **List models & pricing** — See all available models
7. **Prompting help** — Best practices for quality results
</intake>

<routing>
| Choice | Workflow | Default Model |
|--------|----------|---------------|
| 1. Generate image | workflows/image.md | flux-pro |
| 2. Generate video | workflows/video.md | kling |
| 3. Animate image | workflows/video.md (with --image) | kling |
| 4. Logo/icon design | workflows/logo.md | recraft-v3 |
| 5. Quick draft | workflows/image.md | flux-schnell |
| 6. List models | Run: `python3 generate.py image -l` and `python3 generate.py video -l` | — |
| 7. Prompting help | references/prompting-guide.md | — |

**Auto-detection:** If the user's request mentions logo, icon, brand mark, or logotype,
automatically route to `workflows/logo.md` — do not use flux-pro for logo work.
</routing>

<quick_reference>
```bash
# Source credentials
source ~/.claude/.env

# Image generation
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-pro -p "Mountain landscape, golden hour, dramatic clouds" -o mountain.webp

# Fast draft ($0.003)
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m flux-schnell -p "Logo design for a tech startup" --preset logo -o logo.webp

# Video from text
python3 .claude/skills/imagevideogen/scripts/generate.py video \
  -m kling -p "Gentle ocean waves on a sandy beach, slow motion" -d 5 -o waves.mp4

# Animate an image
python3 .claude/skills/imagevideogen/scripts/generate.py video \
  -m kling -p "Subtle head nod and gentle smile" -i portrait.png -o animated.mp4

# Logo/icon design (always use recraft-v3)
python3 .claude/skills/imagevideogen/scripts/generate.py image \
  -m recraft-v3 -p "Minimalist geometric logo mark of a column, flat colors" --preset logo -o logo.png

# List available models
python3 .claude/skills/imagevideogen/scripts/generate.py image --list-models
python3 .claude/skills/imagevideogen/scripts/generate.py video --list-models
```
</quick_reference>

<model_comparison>
### Image Models

| Model | Cost | Speed | Best For |
|-------|------|-------|----------|
| flux-pro | $0.04/img | ~5s | Photorealism, general purpose, highest quality |
| flux-schnell | $0.003/img | ~1s | Fast drafts, iteration, low cost |
| sdxl | $0.008/img | ~8s | Versatile, wide style range, LoRA support |
| recraft-v3 | $0.04/img | ~5s | Vector art, logos, icons, illustrations |

### Video Models

| Model | Cost | Duration | Best For |
|-------|------|----------|----------|
| kling | $0.07/s | 5-10s | Silent video, micro-expressions, portraits |
| minimax | $0.12/s | 5s | Atmospheric scenes, cinematic quality |
| luma | $0.032/s | 5s | Physics-aware motion, nature, fast gen |
| veo | $0.40/s | 5-8s | Highest quality, dialogue audio generation |
</model_comparison>

<reference_index>
- `references/prompting-guide.md` — Image and video prompting best practices
- `references/ui-design-guide.md` — UI/product visual prompt recipe adapted from the UX Planet article
- `references/models.md` — Detailed model comparison and parameters
- `references/troubleshooting.md` — Common errors and fixes
</reference_index>

<workflows_index>
- `workflows/setup.md` — First-time setup and token configuration
- `workflows/image.md` — Image generation walkthrough
- `workflows/video.md` — Video generation and animation walkthrough
- `workflows/logo.md` — Logo/icon design with recraft-v3 + logosystem.co inspiration
</workflows_index>

<success_criteria>
- Output file exists and is non-empty
- Image dimensions match requested (or model default)
- Video plays without corruption
- Cost logged for user awareness
- No API errors in stderr
</success_criteria>
