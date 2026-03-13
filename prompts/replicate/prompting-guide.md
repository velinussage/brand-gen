# Prompting Guide

Quick reference for writing effective generation prompts.

## Image Prompts

### Master Template

**Subject + Style + Lighting + Composition + Details**

Each element adds specificity. More elements = more control over output.

| Element | Examples |
|---------|----------|
| Subject | "A golden retriever", "Modern office building", "Abstract geometric pattern" |
| Style | "Photorealistic", "Watercolor painting", "Minimalist vector", "Oil painting" |
| Lighting | "Golden hour", "Studio softbox", "Dramatic chiaroscuro", "Neon glow" |
| Composition | "Rule of thirds", "Centered", "Wide angle", "85mm portrait lens", "Bird's eye view" |
| Details | "4K", "Shallow depth of field", "Warm color palette", "Matte finish" |

### Quality Boosters

Add these to most prompts for better results:

- `high detail` / `highly detailed`
- `professional quality`
- `sharp focus`
- `4K` / `8K resolution`

### Style Descriptors

**Photography:** photorealistic, DSLR, mirrorless, film grain, Kodak Portra, Fujifilm
**Digital Art:** digital painting, concept art, matte painting, CGI render
**Traditional:** oil painting, watercolor, charcoal sketch, pencil drawing, ink wash
**Design:** vector art, flat design, minimalist, geometric, isometric
**Specific Looks:** cyberpunk, vaporwave, art nouveau, art deco, brutalist

### Negative Prompts

Use `-n` to exclude unwanted elements. Common negatives by category:

**General quality:** `blurry, low quality, watermark, text, logo, oversaturated, underexposed`
**Portraits:** `deformed face, extra fingers, distorted features, uncanny valley`
**Products:** `cluttered background, shadows, reflections, text overlay`
**Landscapes:** `people, urban elements, power lines, watermark`

### Model-Specific Tips

**flux-pro** — Best with natural language. Handles complex scenes well. Prompt upsampling enabled by default.
**flux-schnell** — Keep prompts shorter (under 50 words). Good for quick iteration before switching to flux-pro.
**sdxl** — Benefits from negative prompts. Good with artistic styles. Supports img2img.
**recraft-v3** — Best for vector/logo work. Be explicit about "flat colors", "clean geometry", "scalable".

## UI / Product Visual Prompts

Adapted from the UX Planet article on UI design prompting:
- `prompts/replicate/ui-design-guide.md`

### UI Prompt Formula

For browser illustrations, product banners, and social/feed visuals use:

**Product truth + Surface type + Presentation context + Style words + Composition rule + Fidelity constraints**

Example:

```text
Use the real product screenshot as the hero asset. Browser-based product interface, minimalistic, flat design, clean UI, subtle light background, refined browser window, airy spacing. Focus on one real product story with a tighter crop on the strongest component. Do not redesign the UI. Do not invent labels or product copy.
```

### High-signal UI keywords

- surface type: `landing page screenshot`, `dashboard screenshot`, `feed view`, `detail view`, `library view`
- presentation context: `browser window`, `desktop app frame`, `product marketing image`
- style words: `minimalistic`, `flat design`, `clean UI`, `airy spacing`, `editorial polish`
- crop words: `tighter crop`, `one clear product story`, `generous whitespace`, `safe margins`

### UI Anti-patterns

- Do not prompt only with style words and no product screenshot reference
- Do not ask for a vague `SaaS dashboard` if you want the real app preserved
- Do not omit the constraint `Do not redesign the UI`
- Do not let the model invent copy, labels, buttons, or fake features

## Video Prompts

### Shot Grammar

**Subject action + Camera movement + Lighting + Atmosphere**

Videos need temporal description — what happens over time.

### Text-to-Video (T2V)

Write 40-80 words describing the full scene:

```
A barista carefully pours steamed milk into a latte, creating a rosetta
pattern on the surface, camera positioned overhead looking down, warm
cafe lighting, steam rising from the cup, shallow depth of field,
wooden counter visible at edges of frame
```

### Image-to-Video (I2V)

Write 20-40 words describing ONLY the motion:

```
Gentle head turn to the right, soft blink, slight smile forming,
hair moving subtly in breeze, steady breathing motion
```

### Camera Movement Reference

| Term | Motion | Best For |
|------|--------|----------|
| Static | No camera movement | Portraits, product close-ups |
| Pan left/right | Horizontal rotation | Revealing scenes, following action |
| Tilt up/down | Vertical rotation | Tall subjects, reveals |
| Dolly in/out | Camera toward/away | Dramatic emphasis, establishing |
| Tracking | Follows subject laterally | Walking scenes, chase sequences |
| Orbit | Circles subject | Products, architectural |
| Crane up/down | Vertical lift/drop | Establishing shots, reveals |
| Handheld | Natural slight shake | Documentary, intimate feel |

### Motion Intensity Words

**Subtle:** gentle, slight, subtle, soft, barely perceptible, delicate
**Moderate:** natural, steady, smooth, gradual, flowing
**Dynamic:** dramatic, energetic, rapid, sweeping, bold, powerful

### Model-Specific Tips

**kling** — Excels at human faces and micro-expressions. For I2V, keep motion subtle. Best at 1:1 aspect ratio.
**minimax** — Prompt optimizer enabled by default. Good with atmospheric descriptions. Use `first_frame_image` for I2V.
**luma** — Physics-aware — good for water, cloth, particles. Fast generation. Keep prompts concise.
**veo** — Highest quality. Only model that generates audio. Good for dialogue scenes. Supports up to 8 seconds.

## Common Mistakes

1. **Too vague** — "a dog" → "A golden retriever puppy sitting on a grassy hill, golden hour lighting"
2. **Contradictory styles** — "photorealistic watercolor" → pick one style
3. **I2V describes image** — "beautiful woman in garden" → "gentle head turn, soft smile"
4. **Missing lighting** — Without lighting info, results look flat and generic
5. **Over-prompting video** — Keep video prompts to single continuous shots, not multi-scene narratives
6. **Ignoring negative prompts** — For sdxl especially, negative prompts significantly improve quality
