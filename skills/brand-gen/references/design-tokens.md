# Design tokens reference

This reference is **fully self-contained**. Content below is copied directly from three source skills (with light editing for cross-reference) so the brand-gen cinematographer, philosopher, and CLI can operate against it without loading anything else.

**Credits**
- Math, algorithms, dark-mode derivation: `dylanfeltus/skills/design-tokens` (MIT-compatible).
- W3C DTCG file layout, Style Dictionary pipeline, platform exports (iOS Swift, Android XML, Figma Tokens Studio): `pbc-os/agent-skills-public/tier-4-growth/brand-identity`.
- Font fallback chain + post-processing discipline: `anthropics/skills/brand-guidelines`.

Consumed by `brand_gen/design_tokens.py` and `bgen export-design-tokens`.

---

## 1. Core philosophy *(from dylanfeltus, verbatim)*

- **Math over taste.** Scales should follow ratios, not arbitrary values.
- **Accessibility by default.** Every text/background combo must pass WCAG AA.
- **Systematic.** Every value should be derivable from a base + ratio.
- **Portable.** Output as CSS custom properties, Tailwind config, or JSON tokens.

---

## 2. Type scale *(from dylanfeltus, verbatim)*

### The formula

```
fontSize = baseFontSize × ratio^step
```

### Recommended ratios

| Ratio | Name | Value | Best for |
|-------|------|-------|----------|
| Minor Second | 1.067 | Tight, minimal difference | Dense UI, dashboards |
| Major Second | 1.125 | Subtle progression | Apps, data-heavy interfaces |
| Minor Third | 1.200 | Balanced, versatile | Most websites, SaaS |
| Major Third | 1.250 | Clear hierarchy | Marketing sites, blogs |
| Perfect Fourth | 1.333 | Strong contrast | Editorial, landing pages |
| Augmented Fourth | 1.414 | Dramatic | Bold designs, portfolios |
| Perfect Fifth | 1.500 | Very dramatic | Hero-heavy designs |

### Generating the scale

Given a base size (typically 16px) and a ratio:

```
Step -2: 16 / ratio² = xs
Step -1: 16 / ratio  = sm
Step  0: 16          = base
Step  1: 16 × ratio  = lg
Step  2: 16 × ratio² = xl
Step  3: 16 × ratio³ = 2xl
Step  4: 16 × ratio⁴ = 3xl
Step  5: 16 × ratio⁵ = 4xl
Step  6: 16 × ratio⁶ = 5xl
```

Round to nearest 0.5px or convert to rem (÷ 16).

### Line-height rules

| Font Size | Line Height | Use |
|-----------|-------------|-----|
| ≤ 14px | 1.6–1.7 | Small text, captions |
| 16–20px | 1.5–1.6 | Body text |
| 20–32px | 1.3–1.4 | Subheadings |
| 32–48px | 1.1–1.2 | Headings |
| 48px+ | 1.0–1.1 | Display/hero text |

**Rule of thumb:** as font size increases, line height decreases.

### Letter-spacing rules

| Size | Letter Spacing | Why |
|------|---------------|-----|
| Small text (≤14px) | `0.01–0.02em` | Slightly open for readability |
| Body text | `0em` (normal) | Don't touch it |
| Subheadings | `-0.01em` | Slightly tighten |
| Headings | `-0.02em` to `-0.03em` | Tighten as size grows |
| Display text | `-0.03em` to `-0.05em` | Tight tracking at large sizes |

### Font weight pairing

| Role | Weight | Tailwind |
|------|--------|----------|
| Body | 400 (Regular) | `font-normal` |
| Body emphasis | 500 (Medium) | `font-medium` |
| Subheading | 600 (Semibold) | `font-semibold` |
| Heading | 700 (Bold) | `font-bold` |
| Display | 800 (Extrabold) | `font-extrabold` |

### Output example (CSS custom properties)

```css
:root {
  --font-size-xs: 0.694rem;    /* 11.1px */
  --font-size-sm: 0.833rem;    /* 13.3px */
  --font-size-base: 1rem;      /* 16px */
  --font-size-lg: 1.2rem;      /* 19.2px */
  --font-size-xl: 1.44rem;     /* 23px */
  --font-size-2xl: 1.728rem;   /* 27.6px */
  --font-size-3xl: 2.074rem;   /* 33.2px */
  --font-size-4xl: 2.488rem;   /* 39.8px */
  --font-size-5xl: 2.986rem;   /* 47.8px */
}
```

---

## 3. Color palette *(from dylanfeltus, verbatim)*

### Step 1: Choose base colors

Every palette needs:

| Token | Purpose | Example |
|-------|---------|---------|
| `primary` | Main brand color, CTAs | Your brand color |
| `neutral` | Text, borders, backgrounds | Gray (warm/cool/pure) |
| `success` | Positive states | Green |
| `warning` | Caution states | Amber/yellow |
| `error` | Destructive states | Red |
| `info` | Informational | Blue (can overlap primary) |

### Step 2: Generate shade scale (50–950)

For each base color, generate a 10-step shade scale. The base color is typically the 500 step.

**Method: HSL manipulation**

Starting from the base HSL:

| Step | Lightness Adjustment | Saturation Adjustment |
|------|---------------------|----------------------|
| 50 | +45% | -30% |
| 100 | +38% | -25% |
| 200 | +28% | -15% |
| 300 | +18% | -5% |
| 400 | +8% | 0% |
| 500 | 0% (base) | 0% (base) |
| 600 | -8% | +5% |
| 700 | -18% | +5% |
| 800 | -28% | 0% |
| 900 | -38% | -10% |
| 950 | -45% | -20% |

Clamp all values: lightness 0–100%, saturation 0–100%.

### Step 3: Semantic token mapping

```css
/* Light mode */
--color-bg: var(--neutral-50);
--color-bg-subtle: var(--neutral-100);
--color-bg-muted: var(--neutral-200);
--color-border: var(--neutral-200);
--color-border-strong: var(--neutral-300);
--color-text-muted: var(--neutral-500);
--color-text-subtle: var(--neutral-600);
--color-text: var(--neutral-900);
--color-text-heading: var(--neutral-950);

--color-primary: var(--primary-600);
--color-primary-hover: var(--primary-700);
--color-primary-bg: var(--primary-50);
--color-primary-text: white;
```

---

## 4. WCAG contrast checking *(from dylanfeltus, verbatim)*

### The formula

```
Contrast ratio = (L1 + 0.05) / (L2 + 0.05)
```

Where L1 = lighter relative luminance, L2 = darker.

### Relative luminance

```
For each channel (R, G, B):
  sRGB = channel / 255
  linear = sRGB / 12.92                       if sRGB ≤ 0.03928
         = ((sRGB + 0.055) / 1.055) ^ 2.4     otherwise

L = 0.2126 × R_linear + 0.7152 × G_linear + 0.0722 × B_linear
```

### WCAG requirements

| Level | Ratio | Applies to |
|-------|-------|-----------|
| AA Normal Text | ≥ 4.5:1 | Body text (< 18px or < 14px bold) |
| AA Large Text | ≥ 3:1 | ≥ 18px regular or ≥ 14px bold |
| AAA Normal Text | ≥ 7:1 | Enhanced accessibility |
| AA UI Components | ≥ 3:1 | Borders, icons, focus rings |

### Quick reference (neutral on white #FFFFFF)

| Shade | Approx Contrast | Passes |
|-------|-----------------|--------|
| 300 | ~2.5:1 | ❌ Decorative only |
| 400 | ~3.5:1 | ✅ Large text, UI |
| 500 | ~4.5:1 | ✅ AA body text |
| 600 | ~6:1 | ✅ AA comfortable |
| 700 | ~8:1 | ✅ AAA body text |

### Checking contrast programmatically

When generating palettes, always verify:

1. `text` (900) on `bg` (50) → must be ≥ 4.5:1
2. `text-muted` (500) on `bg` (50) → must be ≥ 4.5:1
3. `primary` (600) on `white` → must be ≥ 4.5:1
4. `primary-text` on `primary` (600) → must be ≥ 4.5:1
5. `border` (200) on `bg` (50) → must be ≥ 3:1

If a combo fails, adjust the darker color one step darker until it passes.

---

## 5. Spacing system *(from dylanfeltus, verbatim)*

### Base-4 scale (recommended)

Everything is a multiple of 4px. Predictable, consistent, works with most font sizes.

```css
:root {
  --space-0: 0px;
  --space-0.5: 2px;
  --space-1: 4px;
  --space-1.5: 6px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;
  --space-24: 96px;
  --space-32: 128px;
}
```

This matches Tailwind's default scale exactly.

### Spacing usage guide

| Context | Spacing | Values |
|---------|---------|--------|
| Inline icon gap | space-1 to space-2 | 4–8px |
| Button padding | space-2 × space-4 | 8px 16px |
| Card padding | space-4 to space-6 | 16–24px |
| Section gap (between elements) | space-6 to space-8 | 24–32px |
| Section padding (container) | space-12 to space-16 | 48–64px |
| Page section vertical rhythm | space-16 to space-24 | 64–96px |

### Container width scale

| Token | Width | Use |
|-------|-------|-----|
| `sm` | 640px | Narrow content (auth forms) |
| `md` | 768px | Blog posts, documentation |
| `lg` | 1024px | App layouts |
| `xl` | 1280px | Wide layouts |
| `2xl` | 1536px | Full-width dashboards |

---

## 6. Dark-mode derivation *(from dylanfeltus, verbatim)*

### The inversion pattern

Don't manually pick dark mode colors. Derive them systematically:

```
Light mode          →  Dark mode
neutral-50  (bg)    →  neutral-950 (bg)
neutral-100 (bg-subtle) → neutral-900 (bg-subtle)
neutral-200 (border) → neutral-800 (border)
neutral-300 (border-strong) → neutral-700 (border-strong)
neutral-500 (text-muted) → neutral-400 (text-muted)
neutral-600 (text-subtle) → neutral-300 (text-subtle)
neutral-900 (text)  →  neutral-50  (text)
neutral-950 (heading) → neutral-50 (heading)
```

**The rule:** Background shades flip (50↔950, 100↔900, 200↔800). Text shades flip similarly. Middle shades (400–600) shift by ~1–2 steps.

### Primary color in dark mode

- Use a lighter step: `primary-400` or `primary-500` instead of `primary-600`
- Reduce saturation slightly for dark backgrounds (avoids eye strain)
- Verify contrast against `neutral-900` or `neutral-950` background

### Semantic tokens for dark mode

```css
/* Light */
:root {
  --color-bg: var(--neutral-50);
  --color-text: var(--neutral-900);
  --color-primary: var(--primary-600);
}

/* Dark */
.dark {
  --color-bg: var(--neutral-950);
  --color-text: var(--neutral-50);
  --color-primary: var(--primary-400);
}
```

Components reference semantic tokens, never raw shades. Switching themes is just swapping the token mapping.

---

## 7. Output formats *(from dylanfeltus, verbatim)*

### CSS custom properties

```css
:root {
  /* Type */
  --font-size-base: 1rem;
  --font-size-lg: 1.2rem;
  /* Colors */
  --color-primary-500: hsl(220, 80%, 50%);
  /* Spacing */
  --space-4: 1rem;
}
```

### Tailwind config

```js
module.exports = {
  theme: {
    extend: {
      fontSize: {
        'xs': '0.694rem',
        'sm': '0.833rem',
        'base': '1rem',
        'lg': '1.2rem',
        'xl': '1.44rem',
      },
      colors: {
        primary: {
          50: 'hsl(220, 50%, 95%)',
          500: 'hsl(220, 80%, 50%)',
          900: 'hsl(220, 60%, 15%)',
        },
      },
    },
  },
}
```

### JSON design tokens (W3C format)

```json
{
  "color": {
    "primary": {
      "500": { "$value": "hsl(220, 80%, 50%)", "$type": "color" }
    }
  },
  "fontSize": {
    "base": { "$value": "1rem", "$type": "dimension" }
  }
}
```

---

## 8. Full W3C DTCG file layout *(from pbc-os tooling-specs, verbatim)*

### Directory layout

```
design-tokens/
├── DESIGN-TOKENS.md                    # Comprehensive documentation (40-55KB)
├── tokens/
│   ├── color.tokens.json               # W3C DTCG format
│   ├── typography.tokens.json
│   ├── spacing.tokens.json
│   ├── elevation.tokens.json
│   ├── radii.tokens.json
│   ├── motion.tokens.json
│   └── breakpoints.tokens.json
├── figma/
│   └── figma-tokens.json               # Tokens Studio for Figma format
├── style-dictionary/
│   ├── config.json                     # Style Dictionary v4 config
│   ├── build.mjs                       # ESM build script
│   └── package.json                    # Dependencies
└── platforms/
    ├── css/
    │   └── variables.css               # Complete CSS custom properties
    ├── tailwind/
    │   └── tokens.config.js            # Tailwind v4 theme extension
    ├── ios/
    │   └── BrandTokens.swift           # Swift UIColor + UIFont extensions
    └── android/
        ├── colors.xml                  # Android color resources
        └── dimens.xml                  # Android dimension resources
```

### W3C DTCG token format

All token files use the W3C Design Tokens Community Group format (https://tr.designtokens.org/format/).

**Structure:**

```json
{
  "tokenGroup": {
    "tokenName": {
      "$value": "the value",
      "$type": "color | dimension | fontFamily | fontWeight | duration | cubicBezier | number | shadow",
      "$description": "What this token is for"
    }
  }
}
```

**Token aliases** use the `{reference.path}` syntax:

```json
{
  "semantic": {
    "text-primary": {
      "$value": "{color.charcoal}",
      "$type": "color",
      "$description": "Primary body text color"
    }
  }
}
```

### Token categories

**color.tokens.json must include:**

- Core palette (all colors from brand brief with exact hex values)
- Extended tint/shade scales (50–900, 10 steps per core color)
- Semantic aliases (`text-primary`, `text-secondary`, `bg-primary`, `bg-secondary`, `bg-elevated`, `border-default`, `border-subtle`, `action-primary`, `action-primary-hover`, `action-secondary`, `success`, `warning`, `error`, `info`)

**typography.tokens.json must include:**

- Font families (display, body, mono) with complete fallback chains
- Font weights (regular, medium, semibold, bold)
- Font sizes (xs through 6xl, in rem)
- Line heights (tight, snug, normal, relaxed)
- Letter spacing (tight, normal, wide, wider)

**spacing.tokens.json must include:**

- Complete scale from 0 to 96 (based on 4px grid), values in rem
- Every step: 0, 1(4px), 2(8px), 3(12px), 4(16px), 5(20px), 6(24px), 8(32px), 10(40px), 12(48px), 16(64px), 20(80px), 24(96px), 32(128px), 40(160px), 48(192px), 64(256px), 80(320px), 96(384px)

**elevation.tokens.json must include:**

- Shadow scale: sm, md, lg, xl, 2xl, inner
- All shadows must use the brand's warm neutral as the shadow color (e.g., `rgba(44, 36, 24, x)` for charcoal-based brands) — **NEVER `rgba(0, 0, 0, x)`**.

**radii.tokens.json must include:**

- Scale: none(0), sm(4px), md(8px), lg(12px), xl(16px), 2xl(24px), full(9999px)

**motion.tokens.json must include:**

- 4 easing curves (default, entrance, exit, emphasis) as cubic-bezier arrays
- 6 durations (micro, short, medium, long, xlong, ambient) in milliseconds

**breakpoints.tokens.json must include:**

- 5 breakpoints (sm, md, lg, xl, 2xl) in pixels

### Figma Tokens Studio format

The `figma/figma-tokens.json` file uses the Tokens Studio format with all token groups in a single file. Include 3–4 composition tokens showing common component patterns (e.g., `button-primary`, `card-default`, `input-default`).

### Style Dictionary v4 config

The `style-dictionary/config.json` must define transforms for:

- CSS (custom properties in `:root`)
- Tailwind (theme extension object)
- iOS Swift (UIColor, CGFloat, String constants)
- Android (colors.xml, dimens.xml)

The `build.mjs` must be a working ESM build script. The `package.json` must list `style-dictionary@^4.0.0` as a dependency.

### Platform export requirements

**CSS (`platforms/css/variables.css`):**

- Complete `:root` block with ALL tokens as custom properties
- Organized with section comments
- Include `@media (prefers-color-scheme: dark)` section (comment placeholder if dark mode not defined)
- Include `@media (prefers-reduced-motion: reduce)` overrides for motion tokens

**Tailwind (`platforms/tailwind/tokens.config.js`):**

- Export default object mapping all tokens to Tailwind theme keys
- Include both Tailwind v3 (`extend`) and v4 (`@theme` CSS) formats

**iOS Swift (`platforms/ios/BrandTokens.swift`):**

- Namespace everything under a `Brand` enum
- `UIColor` extensions for all colors
- `CGFloat` constants for spacing and radii
- `UIFont` helpers for the type scale
- UIKit + SwiftUI compatible

**Android (`platforms/android/`):**

- `colors.xml`: All colors in `#AARRGGBB` format, with semantic aliases as `@color/` references
- `dimens.xml`: Spacing in dp, font sizes in sp, radii in dp

---

## 9. Smart font application *(from anthropics/brand-guidelines, verbatim)*

### Colors — main

- Dark: `#141413` — primary text and dark backgrounds
- Light: `#faf9f5` — light backgrounds and text on dark
- Mid Gray: `#b0aea5` — secondary elements
- Light Gray: `#e8e6dc` — subtle backgrounds

### Colors — accents

- Orange: `#d97757` — primary accent
- Blue: `#6a9bcc` — secondary accent
- Green: `#788c5d` — tertiary accent

### Typography

- **Headings:** Poppins (with Arial fallback)
- **Body text:** Lora (with Georgia fallback)
- **Note:** Fonts should be pre-installed in your environment for best results

### Smart font application (the rule)

- Applies Poppins font to headings (24pt and larger)
- Applies Lora font to body text
- Automatically falls back to Arial/Georgia if custom fonts unavailable
- Preserves readability across all systems

### Text styling

- Headings (24pt+): Poppins font
- Body text: Lora font
- Smart color selection based on background
- Preserves text hierarchy and formatting

### Shape and accent colors

- Non-text shapes use accent colors
- Cycles through orange, blue, and green accents
- Maintains visual interest while staying on-brand

### Font management (technical)

- Uses system-installed Poppins and Lora fonts when available
- Provides automatic fallback to Arial (headings) and Georgia (body)
- No font installation required — works with existing system fonts
- For best results, pre-install Poppins and Lora fonts in your environment

### Color application (technical)

- Uses RGB color values for precise brand matching
- Applied via python-pptx's `RGBColor` class
- Maintains color fidelity across different systems

### Brand-gen application of this pattern

For every font declared in `identity.json`, emit the full fallback chain instead of a single family name:

```
Headings: "Poppins", Arial, sans-serif
Body:     "Lora", Georgia, serif
Mono:     "JetBrains Mono", Menlo, monospace
```

Rules:

- Heading sizes start at 24 pt (or equivalent); smaller text stays in the body stack.
- Never emit a single font name without a generic family fallback.
- In HTML share cards, emit the full fallback chain in CSS `font-family`.
- In PPTX / Keynote exports, use the python-pptx fallback mechanism — don't assume custom fonts are available on the render host.
- Shape accents cycle through accent colors (never reuse one accent twice adjacent).

---

## 10. Step-by-step token setup *(from dylanfeltus, verbatim)*

1. **Ask:** What's the project? (marketing site, SaaS app, dashboard?)
2. **Type scale:** Pick ratio based on project type → generate scale
3. **Colors:** Get brand color → generate shade scales for primary + neutral + semantic
4. **Verify contrast:** Check all text/bg combos against WCAG AA
5. **Spacing:** Use base-4 scale (match Tailwind)
6. **Dark mode:** Derive from light palette using inversion pattern
7. **Output:** Generate CSS custom properties and/or Tailwind config

### Example 1: "Set up design tokens for a SaaS dashboard"

- Type: Minor Third (1.2) ratio, 16px base — clear hierarchy without being dramatic
- Colors: Generate from brand blue, warm gray neutral
- Spacing: Base-4 (Tailwind default)
- Dark mode: Full derivation

### Example 2: "I need a color palette from this brand color: #6366F1"

- Parse HSL: ~239°, 84%, 67%
- Generate 50–950 scale using the shade generation method
- Map semantic tokens
- Verify WCAG contrast for all text/bg combos
- Output as CSS + Tailwind config

### Example 3: "Create a type scale for a blog"

- Ratio: Major Third (1.25) — strong hierarchy for editorial content
- Base: 18px (slightly larger for long-form reading)
- Generate scale with line-height and letter-spacing for each step

---

## 11. brand-gen identity.json → tokens mapping

Brand-gen stores the source material in `identity.json`. The `build_tokens()` helper in `brand_gen/design_tokens.py` maps:

| identity.json field | Token group |
|--------------------|-------------|
| `brand_colors.primary` | `color.primary.{50..950}` generated via §3 scale |
| `brand_colors.secondary` | `color.secondary.{50..950}` |
| `brand_colors.accents[]` | `color.accent-{i}.{50..950}` |
| `brand_colors.neutral` (optional) | `color.neutral.{50..950}` (derive a warm/cool grey from primary if absent) |
| `typography.headings` | `typography.fontFamily.display` + Arial fallback |
| `typography.body` | `typography.fontFamily.body` + Georgia fallback |
| `typography.mono` (optional) | `typography.fontFamily.mono` + Menlo fallback |
| `typography.type_scale_ratio` (optional) | ratio for §2 math (default 1.200 / Minor Third) |
| `typography.base_size_px` (optional) | base for §2 (default 16) |
| `layout.spacing_base` (optional) | default 4 (§5) |
| `layout.radius_base` (optional) | default 8 (§8 radii) |
| `messaging.forbidden_claims` | no token impact; stays in prompt-prelude |

Missing fields fall back to sensible defaults from §2–§8.

---

## 12. Validation gate

`brand_gen/design_tokens.py` runs the five checks from §4 before writing output. Failures are reported as warnings (build proceeds) or errors (build stops):

1. `text` on `bg` ≥ 4.5 — **error** if not
2. `text-muted` on `bg` ≥ 4.5 — **error** if not
3. `primary` on white ≥ 4.5 — **warning** if not (primary buttons may still have white text; check #4)
4. `primary-button-text` on `primary` ≥ 4.5 — **error** if not
5. `border` on `bg` ≥ 3.0 — **warning** if not

Reporting follows `brand_gen/seedance_validation.py`: an `AuditResult(ok, errors, warnings, checks)` dataclass with a `.report()` renderer.

---

## 13. Using this reference as a brand-gen agent

1. Read `identity.json` → extract primary / neutral / fonts / optional overrides.
2. Call `brand_gen.design_tokens.build_tokens(identity)` → structured token dict.
3. Call `wcag_audit(tokens)` → list of violations.
4. If AA errors: adjust shades one step darker per §4, recheck. Stop after 2 cycles.
5. Call `emit(tokens, fmt)` for each requested format (`"css" | "tailwind" | "json" | "w3c"`).
6. Write files to `.brand-gen/brands/<brand>/design-tokens/`.

The `bgen export-design-tokens` CLI wraps steps 1–6. Direct module access is for custom pipelines (e.g. `card_engine.py` consuming tokens in-process for the HTML share-card renderer).
