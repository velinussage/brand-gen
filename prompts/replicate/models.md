# Model Reference

Detailed comparison of all supported models.

## Image Models

### flux-pro (Recommended Default)

| Property | Value |
|----------|-------|
| Replicate ID | `black-forest-labs/flux-1.1-pro` |
| Cost | $0.04/image |
| Output Format | WebP |
| Default Size | 1024x1024 |
| Prompt Upsampling | Enabled by default |

**Best for:** Photorealism, general purpose, complex scenes, highest quality output.

**Strengths:** Excellent prompt following, natural language understanding, consistent quality. Handles multi-subject scenes well.

**Limitations:** No negative prompt support. No img2img. Higher cost than schnell.

**Parameters:**
- `width` / `height` — Output dimensions (default: 1024x1024)
- `prompt_upsampling` — Auto-enhance prompts (default: true)
- `safety_tolerance` — 0-6, lower = stricter (default: 2)
- `seed` — Reproducibility

---

### flux-schnell

| Property | Value |
|----------|-------|
| Replicate ID | `black-forest-labs/flux-schnell` |
| Cost | $0.003/image |
| Output Format | WebP |
| Default Size | 1024x1024 |

**Best for:** Fast drafts, iteration, low-cost exploration, testing prompts.

**Strengths:** Very fast generation (~1-2s). Extremely cheap. Good enough for draft quality.

**Limitations:** Lower quality than flux-pro. Not recommended for final outputs.

**Parameters:**
- `width` / `height` — Output dimensions (default: 1024x1024)
- `num_inference_steps` — Steps (use `--steps` flag)
- `seed` — Reproducibility

---

### sdxl

| Property | Value |
|----------|-------|
| Replicate ID | `stability-ai/sdxl` |
| Cost | $0.008/image |
| Output Format | PNG |
| Default Size | 1024x1024 |

**Best for:** Wide style range, artistic outputs, img2img, LoRA support.

**Strengths:** Supports negative prompts. Supports img2img (style transfer). Good with artistic and stylized outputs. Fine-grained control via guidance scale and steps.

**Limitations:** Less consistent than Flux for photorealism. Can require more prompt engineering.

**Parameters:**
- `width` / `height` — Output dimensions (default: 1024x1024)
- `num_inference_steps` — Steps (default: 25, use `--steps` flag)
- `guidance_scale` — Prompt adherence (default: 7.5, use `--guidance-scale` flag)
- `negative_prompt` — What to avoid (use `-n` flag)
- `image` — Input image for img2img (use `-i` flag)
- `seed` — Reproducibility

---

### recraft-v3

| Property | Value |
|----------|-------|
| Replicate ID | `recraft-ai/recraft-v3` |
| Cost | $0.04/image |
| Output Format | PNG |

**Best for:** Vector art, logos, icons, illustrations, design assets.

**Strengths:** Clean geometric output. Excellent for brand and design work. Scalable-looking results.

**Limitations:** Not great for photorealism. Higher cost.

**Parameters:**
- `width` / `height` — Output dimensions
- `seed` — Reproducibility

---

## Video Models

### kling

| Property | Value |
|----------|-------|
| Replicate ID | `kwaivgi/kling-v2.5-turbo-pro` |
| Cost | $0.07/second |
| Output Format | MP4 |
| Default Duration | 5 seconds |
| Default Aspect Ratio | 1:1 |

**Best for:** Portrait animation, micro-expressions, subtle human motion, I2V.

**Strengths:** Best facial detail and micro-expression quality. Excellent for headshot animation. Good temporal consistency.

**Limitations:** Best at shorter durations. 1:1 default aspect ratio.

**Parameters:**
- `duration` — Video length in seconds (use `-d` flag)
- `aspect_ratio` — Output ratio (use `-ar` flag, default: 1:1)
- `start_image` — Image to animate (use `-i` flag)
- `seed` — Reproducibility

---

### minimax

| Property | Value |
|----------|-------|
| Replicate ID | `minimax/video-01-live` |
| Cost | $0.12/second |
| Output Format | MP4 |

**Best for:** Atmospheric scenes, cinematic quality, mood-driven content.

**Strengths:** Built-in prompt optimizer. Rich lighting and atmosphere. Good cinematic quality.

**Limitations:** Higher cost. Slower generation.

**Parameters:**
- `prompt_optimizer` — Auto-enhance prompts (default: true)
- `first_frame_image` — Image to animate (use `-i` flag; mapped automatically)
- `seed` — Reproducibility

---

### luma

| Property | Value |
|----------|-------|
| Replicate ID | `luma/ray-2-flash` |
| Cost | $0.032/second |
| Output Format | MP4 |

**Best for:** Physics-aware motion, nature scenes, water/cloth/particles, fast generation.

**Strengths:** Realistic physical motion. Fast generation. Good value for cost. Excellent for natural phenomena.

**Limitations:** Max ~5 seconds. Less precise facial detail than kling.

**Parameters:**
- Standard prompt and image inputs
- `seed` — Reproducibility

---

### veo

| Property | Value |
|----------|-------|
| Replicate ID | `google/veo-3` |
| Cost | $0.40/second |
| Output Format | MP4 |
| Default Duration | 8 seconds |

**Best for:** Highest quality video, dialogue scenes, generated audio, premium output.

**Strengths:** Only model with generated audio/sound. Highest overall quality. Supports longer clips. Good for dialogue and speaking subjects.

**Limitations:** Very expensive. Slower generation. Cost adds up quickly.

**Parameters:**
- `duration` — Video length in seconds (default: 8, use `-d` flag)
- `seed` — Reproducibility

---

## Cost Comparison

### Image (per generation)

| Model | Cost | Speed | Quality |
|-------|------|-------|---------|
| flux-schnell | $0.003 | Fast (1-2s) | Draft |
| sdxl | $0.008 | Medium (5-10s) | Good |
| flux-pro | $0.04 | Medium (5-10s) | Excellent |
| recraft-v3 | $0.04 | Medium (5-10s) | Excellent (design) |

### Video (per second of output)

| Model | $/sec | 5s Cost | 8s Cost | Quality |
|-------|-------|---------|---------|---------|
| luma | $0.032 | $0.16 | $0.26 | Good |
| kling | $0.07 | $0.35 | $0.56 | Excellent (faces) |
| minimax | $0.12 | $0.60 | $0.96 | Excellent (atmosphere) |
| veo | $0.40 | $2.00 | $3.20 | Premium + audio |
