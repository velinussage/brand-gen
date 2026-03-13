# Feature Animation Brief

Use this when turning a browser illustration, banner, or product visual into motion.

## Inputs
- Chosen static concept
- Brand description
- Motion goal
- Duration target
- Platform / placement

## Motion rules
- Preserve the real UI structure; do not redesign or rewrite it during motion treatment
- Prefer subtle premium motion over chaotic distortion
- Keep browser / interface edges readable
- Use smooth reveal timing and a confident final hold
- Animate one clear story per clip
- Preserve the brand palette and typography hierarchy
- Animate only the approved still or approved product crop
- Do not add new product panels during motion
- Use Ramotion boldness in the reveal, MetaLab restraint in the hold
- If the still is compositionally weak, fix the still first; motion should not be used to hide a mid layout
- A feature animation should start from a true styleframe or feature illustration, not a generic screenshot package

## Better motion-prompt structure
For motion, do not use one loose paragraph full of mood words.

Use this structure:
1. subject truth
2. start frame
3. one motion idea
4. camera rule
5. timing / beat map
6. end frame
7. negative prompt

Template:

```text
Subject: [exact mark / exact UI crop / exact poster still]
Start frame: [what the viewer sees at frame 1]
Motion: [one verb only: reveal, draw-on, parallax, pulse, slide, sweep]
Camera: [locked / subtle push-in / subtle drift]
Timing: [0-1s, 1-3s, 3-5s]
End frame: [what must be perfectly readable]
Negative: [what must never happen]
```

## Kling-specific guidance
When using Kling-style image-to-video models:
- treat the starting still as sacred
- lock the final frame to the real logo or approved still
- use one reveal idea only
- keep the camera locked unless the reference motion clearly calls for a subtle push
- preserve edges and silhouette above atmosphere
- if available, prefer motion-control workflows for logo bumpers over generic text-only prompting

## Brand bumper / stinger rule
For logo or brand bumpers:
- preserve exact mark recognition
- use one reveal idea only
- keep palette discipline and silhouette truth
- do not add extra symbols, fake text, or generic 3D logo-spin behavior

Recommended structure for logo bumpers:
- 0.0–0.8s: quiet pre-roll / field settle
- 0.8–2.5s: one reveal action
- 2.5–4.5s: mark resolves cleanly
- 4.5–5.5s: final hold

Avoid:
- constant camera motion
- multiple reveal ideas in one clip
- morphing into unrelated symbols
- fake metallic extrusion
- glow explosions
- text that appears only because the model invented it

## Useful directions
- Browser window reveal
- Ribbon-like logo draw-on
- Gentle product parallax
- Interface highlight sweep
- Soft card / panel motion loop
- Poster-like field with one moving product crop
