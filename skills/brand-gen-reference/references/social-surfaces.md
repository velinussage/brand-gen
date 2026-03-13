# Social and feed surfaces

Prefer the live command for current output:

```bash
python3 mcp/brand_iterate.py social-specs
```

## Working defaults in brand-gen

| Surface | Size | Ratio | Best use |
|---|---:|---:|---|
| X card | `1200x600` | `2:1` | Link-card style announcement or illustrated product card |
| X feed (landscape) | `1600x900` | `16:9` | Wide feature/product post |
| X feed (square) | `1080x1080` | `1:1` | Portable cross-platform post |
| X feed (portrait) | `1080x1350` | `4:5` | Taller mobile-first product visual |
| LinkedIn card | `1200x627` | `1.91:1` | Cleaner editorial product communication |
| LinkedIn feed (landscape) | `1200x627` | `1.91:1` | Native feed post with more breathing room |
| LinkedIn feed (square) | `1080x1080` | `1:1` | Cross-platform square format |
| LinkedIn feed (portrait) | `627x1200` | `1:1.91` | Taller LinkedIn-native post |
| OG card | `1200x630` | `1.91:1` | Safe universal preview image |

## Practical guidance

- `x-feed` — bold, fast, legible in-feed; keep the copy system short and brand-forward.
- `linkedin-feed` — calmer hierarchy, cleaner proof framing, more trust/editorial tone.
- `og-card` — one branded statement and immediate recognition; avoid overloading it.

## Composition notes

- X / feed surfaces want stronger headline-safe space and quicker legibility.
- LinkedIn usually benefits from more breathing room and less aggressive contrast stacking.
- OG should be treated as a preview surface, not as a dense poster.

## Copy / messaging rules

- Feed materials are usually **copy-bearing**. Run `ideate-messaging` / `ideate-copy` first.
- Do not let the actual UI heading become the accidental campaign headline.
- If the user wants exact wording, solve copy before image generation.

## Source confidence

- X card preset is based on official X card documentation.
- LinkedIn landscape/square/portrait feed presets align to current official LinkedIn single-image specs.
- X feed landscape/square/portrait presets are brand-gen working defaults chosen for practical composition, not one official organic-feed spec.
- OG `1200x630` is a practical cross-platform default.

## Gotchas

- When a user asks for exact dimensions, use `social-specs` instead of trusting memory.
- `1.91:1` may not be usable on every model backend; if a model rejects it, switch to a supported ratio or a deterministic compose path.
