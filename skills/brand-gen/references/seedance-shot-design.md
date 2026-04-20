# Seedance shot-design reference

Distilled English-only reference for brand-gen video materials. Source: `openclaw/skills` → `woodfantasy/seedance-shot-design` v1.9.0 (MIT-compatible, credit retained). Full upstream skill is installed at `.agents/skills/woodfantasy/seedance-shot-design/` — load that for Chinese-first workflows, long-form (>15s) segmentation, I2V variance rules, and platform specs.

This trimmed reference is loaded by the `brand-cinematographer` agent and by `brand-philosopher` when establishing a brand's "motion grammar".

---

## 1. Four-axis director decomposition

When a director style is invoked, break it into four physical axes. The final prompt must never name the director — only the axes.

| Axis | What it controls | Example phrases |
|------|------------------|-----------------|
| Palette | Color temperature, saturation, grade | `desaturated steel-blue and charcoal`, `teal-and-orange split` |
| Lighting | Source type, behavior, atmosphere | `heavy atmospheric haze with volumetric god rays`, `low-key single-source carving face from darkness` |
| Art direction | Architecture, materials, staging | `brutalist concrete architecture`, `miniature dollhouse set design` |
| Camera | Focal length, movement, stabilization | `glacial push-in on 135mm telephoto`, `strict symmetrical centered composition` |

**Rule:** The assembled prompt contains only axis phrases. It never contains director names, studio names, or IP titles.

---

## 2. Director style library (safe prompt lines, English only)

Pick one token per video to anchor brand mood. Never combine more than one.

### Cold-realist institutional weight
`IMAX 65mm film grain, desaturated steel-blue and charcoal palette, high-contrast natural key lighting, monumental practical-scale architecture, glacial dolly push-in, heavy debris particle physics, zero handheld shake`

### Monumental compression and atmospheric scale
`Brutalist concrete architecture, monolithic scale with tiny human figure for contrast, heavy atmospheric haze with volumetric god rays, desaturated amber-sand palette, glacial push-in on 135mm telephoto, oppressive silence`

### Symmetric storybook flat-stage
`Strict symmetrical centered composition, flat theatrical staging with zero depth perspective, pastel macaron palette (mustard yellow, powder pink, mint green), mechanical 90-degree lateral dolly, miniature dollhouse set design, soft even fill lighting with no hard shadows`

### Neon voyeuristic step-print
`Step-printed slow motion with ghosting trails, voyeuristic foreground obstruction (door frames, curtains, glass), neon teal-and-orange split lighting, smoldering atmospheric haze, claustrophobic tight framing, rain-soaked reflective surfaces, slow shutter drag with motion blur`

### Hand-painted pastoral warmth
`Hand-painted watercolor cel animation, soft diffused natural sunlight through cumulus clouds, expansive 70% sky composition, lush green-and-sky-blue pastoral palette, gentle breeze rippling grass and hair, slow pan across meadow, warm nostalgic golden-hour tones`

### Clinical low-key precision
`Low-key single-source lighting carving face from darkness, desaturated sickly green-grey palette, precise mechanical dolly tracking with zero handheld, clinical digital texture, oppressive controlled framing, subject slightly off-center creating unease`

### Available-light natural restraint
`Natural window light as sole source, golden-hour warmth with soft shadow falloff, layered spatial depth using atmospheric haze between planes, slow contemplative dolly, available-light skin tones, floating dust particles catching light, minimal intervention restrained beauty`

### Weather-as-narrative chiaroscuro
`Torrential rain as dominant lighting source and narrative force, ensemble figures in directional formation, 200mm telephoto compressing depth, mud splashing with each footstep, banners whipping violently in storm wind, slow-motion arc with droplets frozen mid-air, high-contrast chiaroscuro`

### Digital-animation sky-gradient
`Digital anime aesthetic, hyper-detailed photorealistic sky with towering cumulus clouds and vivid blue-to-orange gradient, dramatic god rays piercing cloud layers, silhouette against golden-hour backlight, crystalline rain droplets catching prismatic light, extreme color saturation, detail insert cuts of water droplets on glass`

---

## 3. Cinematography dictionary — safe English phrases

Bare words `Dolly`, `Aerial`, `Crane`, `Pan`, `Arc`, `Dutch`, `Steadicam` can be misclassified as names by Seedance's moderation. Always use full phrases.

### Shot sizes
Extreme close-up (ECU) · close-up (CU) · medium close-up (MCU) · medium shot (MS) · medium full shot · full shot (FS) · wide shot (WS) · extreme wide shot (EWS) · establishing shot · over-the-shoulder (OTS) · two-shot · POV shot.

### Camera moves — safe phrasings
- `pan shot` (horizontal rotation)
- `tilt up` / `tilt down`
- `dolly tracking shot` / `dolly push-in` / `dolly pull-out`
- `zoom in` / `zoom out`
- `truck left` / `truck right`
- `crane shot` / `jib shot`
- `orbital camera movement` / `arc shot`
- `tracking shot`
- `static shot` / `locked-off shot`
- `slow push-in` / `slow pull-out`
- `pedestal up` / `pedestal down`
- `epic drone reveal shot` (slow rise from low angle behind subject)
- `reveal through obstacle shot` (camera pushing through obstruction)
- `leading shot pulling back` (camera retreats ahead of subject)
- `FPV drone shot` (sharp banking, motion blur)
- `Steadicam follow` (organic breathing motion)
- `SnorriCam body-mounted` (subject static, world rushes)
- `crash cam ground level`
- `whip pan transition`
- `snap zoom` / `crash zoom`

### Style modifiers (stack with moves)
Speed: `smooth`, `slow`, `rapid`, `subtle`, `gradual`, `sudden`.
Mood: `cinematic`, `intimate`, `epic`, `dreamy`, `aggressive`, `dynamic`.
Stabilization: `handheld`, `gimbal`, `Steadicam`, `aerial drone shot`, `POV`, `FPV drone`, `Dutch angle`.

### Focal length (mm beats adjectives — the model responds to numbers)
- `14mm ultra-wide lens` — compression panic, barrel distortion, oppressive interiors
- `24-35mm` — natural environmental establishing
- `50mm standard lens` — eye-level, documentary truth
- `85mm portrait lens` — shallow DOF, intimate warmth
- `135mm telephoto lens` — creamy bokeh, micro-expressions
- `200mm+ super telephoto` — surveillance, voyeuristic compression
- `Fisheye` — spherical distortion, psychological warp

### Focus-pull vocabulary
`Slow rack focus` · `snap focus` / `whip focus` · `breathing focus` · `shallow depth of field` · `deep focus`.

Combine telephoto + rack focus for maximum drama:
`135mm telephoto, shallow DOF, slow rack focus from wilting flower in foreground to subject's face in background, creamy bokeh transition`

---

## 4. Three-layer lighting recipe

Every Seedance prompt should name lighting in three layers. Missing any layer = a flat, plastic image.

### Layer 1 — Source (what light, from where)
Catastrophe: `storm backlight` · `explosion orange-red firelight` · `nuclear white` · `lightning side-flash`.
Fantasy: `self-emissive magical glow` · `ritual circle halo` · `mist-filtered light` · `cold moonlight`.
Sci-fi: `engine tail-flare light` · `blue-white energy orb` · `holographic scatter`.
Urban night: `neon diffused wash` · `glass-curtain reflections` · `streaking car lights` · `alarm-red spill`.
Natural: `golden-hour side-backlight` · `overcast diffused sky light` · `cold moonlight` · `flickering firelight`.
Interior: `desk-lamp side light` · `window-side spill` · `candle flicker` · `cold screen glow`.

### Layer 2 — Behavior (how light interacts with matter/atmosphere)
`Haze softening highlights` · `fog deepening shadow contrast` · `volumetric god rays through dust` · `volumetric light shafts` · `particle scatter through smoke` · `prismatic refraction through glass` · `sharp metal specular` · `wet-surface neon bleed` · `subsurface scattering through skin or jade`.

### Layer 3 — Color grade (overall mood)
- Disaster: cold blue base + lava-red highs
- Cyberpunk: cold blue base + neon magenta highs
- Fantasy: dark-cyan base + gold/fluorescent highs
- Post-apocalypse: grey-green base + blood-red pushes
- Epic warm: dark umber base + orange-gold highs
- High-grey restraint: low-saturation grey + warm micro-lifts
- Dreamlike: soft-pink base + gold micro-lifts
- Social rich: high saturation + strong contrast + warm bias

### Four complete recipes
| Scene | Recipe |
|-------|--------|
| Product hero | `Studio hero lighting, 45-degree key with soft fill, rim light outlining silhouette, gradient backdrop` |
| Neon street | `Neon multi-source lighting, wet-surface reflections, rim spill from storefronts, blue-purple ambient fill` |
| Car interior | `Dashboard glow lighting face from below, passing streetlight sweeps across interior, rearview reflections` |
| Stage / concert | `Follow-spot key, colored gel wash from sides, dry-ice floor fog catching laser beams, strobe accent` |

---

## 5. Anti-plastic quality anchors

### Banned filler words (remove if present)
`4K`, `8K`, `masterpiece`, `best quality`, `ultra HD`, `extremely detailed`, `hyper-realistic`, `super resolution`, `ultra-sharp`. They overdrive the sharpen/denoise path and produce the plastic-CG look.

### Substitute with physical-medium anchors

#### Render engines (pick one)
`UnrealEngine 5`, `Octane physical render`, `Blender Cycles`, `V-Ray raytrace`, `Houdini particle sim`, `Cel-shaded toon render`.

#### Camera bodies
`ARRI ALEXA color`, `RED camera`, `65mm film grain`, `35mm film grain`, `16mm film grain`.

#### Film stocks (each has a real color signature)
| Stock | Phrase | Signature |
|-------|--------|-----------|
| Kodak Portra 400 | `Shot on Kodak Portra 400` | Warm natural skin, low contrast — kills AI waxy face |
| Cinestill 800T | `Shot on Cinestill 800T` | Warm, red halation around neon — cyberpunk |
| Kodak Vision3 500T | `Shot on Kodak Vision3 500T` | Industry-standard cinematic color |
| Fuji Pro 400H | `Shot on Fuji Pro 400H` | Cool mint-green bias, soft highs |
| Kodak Ektachrome E100 | `Shot on Kodak Ektachrome E100` | Saturated slide-film retro |

#### Organic imperfections (use at least one per prompt)
`Cinematic halation` · `anamorphic lens flares` · `barrel distortion` · `natural optical vignetting` · `realistic skin texture with visible pores and micro-imperfections` · `sweat glistening on skin surface` · `floating dust particles caught in light` · `fabric micro-fiber detail under light` · `individual hair strands catching light` · `rain droplets trickling down glass` · `condensation fog on cold surfaces` · `dust motes drifting through shafts of light`.

### Material texture swap
| Material | Phrase |
|----------|--------|
| Skin | `Realistic skin texture with visible pores, subsurface scattering, micro-imperfections` |
| Hair | `Individual hair strands with flyaway wisps, translucent backlit edges` |
| Silk | `Flowing silk with specular micro-highlights, liquid-smooth draping, light transmission` |
| Brushed metal | `Brushed metal with anisotropic reflection, micro-scratched surface, sharp specular` |
| Glass | `Transparent glass with caustic light patterns, refractive distortion, fingerprint smudges` |
| Food | `Glistening food surface with oil sheen, steam wisps rising, juice droplets beading` |
| Jade | `Jade with deep subsurface scattering, waxy luster, translucent green-white gradation` |
| Stone | `Rough-hewn stone with granular surface, moss in crevices, weathered patina` |

---

## 6. Six-element assembly template

```
[Subject and appearance detail] +
[Action with physical coherence] +
[Setting / environment] +
[Visual style / lighting] +
[Focal length + camera move] +
[Native audio request]
```

Length sweet spot: 60–100 English words. Shorter = under-specified. Over 100 = concept drift.

For anything longer than 5 seconds, split into time slices on their own lines:
```
0-3s: [slice]
3-7s: [slice]
Lighting: [source], [behavior], [grade].
SFX: [cue]
Negative: any text, subtitles, logos or watermarks
```

Each slice gets **one subject action + one camera move**. Never stack two camera moves in the same slice.

Use present-continuous tense for English action verbs: `a figure running through rain` (not `runs`).

---

## 7. Motion intensity vocabulary

Stops the "motion mush" failure where AI video under-moves.

| Intensity | English modifiers |
|-----------|-------------------|
| Explosive | `violent`, `explosive`, `slamming`, `bursting` |
| Dramatic | `dramatic`, `vigorous`, `rapid`, `forceful` |
| Sudden | `sudden`, `abrupt`, `snapping`, `jolting` |
| Steady | `steady`, `confident`, `natural`, `brisk` |
| Gentle | `gentle`, `soft`, `smooth`, `delicate` |
| Gradual | `gradual`, `slowly`, `imperceptibly`, `easing` |

Every action carries an intensity modifier. Every camera move matches the action's intensity (don't pair `violent` action with `gentle` camera).

---

## 8. Seven-rule validation checklist (hard gate before handoff)

A prompt only ships if **all seven pass**.

1. **Length** — ≤1000 English words. Over = reject.
2. **Time slices** — if declared duration > 5s, must have numbered time slices starting at 0.
3. **Camera literacy** — at least one camera phrase from §3 present.
4. **Filler banned** — no `4K`, `8K`, `masterpiece`, `best quality`, `ultra-sharp`, `hyper-realistic`, `ultra HD`. Reject if present.
5. **Asset caps** — ≤9 image refs, ≤3 video refs, ≤3 audio refs, ≤12 combined.
6. **Conflict scan** — no `slow motion` + `speed ramp` in the same slice. No `14mm ultra-wide` + `shallow DOF`. No `handheld` + `strict symmetrical`. No film-stock + `ultra-sharp digital`. No cel-shaded + photoreal PBR (pick one).
7. **Bare-word scrub** — no standalone `Dolly` / `Aerial` / `Crane` / `Pan` / `Arc` / `Dutch` / `Steadicam`. Always full phrase.

If anything fails, rewrite and re-validate. Never ship a prompt that hasn't passed all seven.

---

## 9. Motion-grammar for brand-gen

When the `brand-philosopher` cultivates a brand's motion grammar, it writes the following block into `custom-scratchpad.md` under a `## Motion grammar` heading:

```markdown
## Motion grammar

Director token (exactly one from §2): <chosen safe-prompt line>

Favored camera moves (3–5 from §3):
- <phrase>
- <phrase>
- <phrase>

Banned camera moves (1–3):
- <phrase>
- <phrase>

Motion intensity default: <one of: explosive / dramatic / sudden / steady / gentle / gradual>

Lighting recipe (three layers):
- Source: <Layer 1 phrase>
- Behavior: <Layer 2 phrase>
- Grade: <Layer 3 phrase>

Film stock / render: <Portra 400 / Cinestill 800T / UnrealEngine5 / etc.>

Quality anchors (at least one organic imperfection):
- <phrase>
- <phrase>

Never use:
- <banned filler words if any specific to this brand>
- <director tokens to avoid>
```

The `brand-cinematographer` agent reads this block before every video generation and assembles all six elements of a Seedance prompt from it, then runs §8 validation before handoff.

---

## 10. Full upstream skill

For scenarios not covered here (short-drama dialog rendering, e-commerce product ads, multi-frame story chains, audio-tag generation, >15s auto-segmentation), load `.agents/skills/woodfantasy/seedance-shot-design/SKILL.md` and its `references/scenarios.md` directly. Those cover ~1100 lines of scenario templates that stay out of this trimmed reference by design.
