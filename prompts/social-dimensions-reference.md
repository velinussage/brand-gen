# Social Dimensions Reference

Current working defaults in this repo:

- **X card**: `1200x600` (`2:1`)
- **X feed (landscape)**: `1600x900` (`16:9`)
- **X feed (square)**: `1080x1080` (`1:1`)
- **X feed (portrait)**: `1080x1350` (`4:5`)
- **LinkedIn card**: `1200x627` (`1.91:1`)
- **LinkedIn feed (landscape)**: `1200x627` (`1.91:1`)
- **LinkedIn feed (square)**: `1080x1080` (`1:1`)
- **LinkedIn feed (portrait)**: `627x1200` (`1:1.91`)
- **OG card**: `1200x630` (`1.91:1`, inferred cross-platform default)

## Notes
- Use X cards for faster, bolder illustrated feature announcements.
- Use X feed presets for organic visual posts where you want square or taller mobile-friendly framing.
- Use LinkedIn cards for cleaner, more editorial product communication.
- Use LinkedIn feed presets when the post is native to the LinkedIn feed rather than a link-preview card.
- Use OG cards as the safest universal preview format when one image must work across multiple link-preview surfaces.

## Source references
- X summary/large image cards: https://developer.x.com/en/docs/x-for-websites/cards/overview/summary-card-with-large-image
- LinkedIn custom link image help: https://www.linkedin.com/help/linkedin/answer/a507663
- LinkedIn single image specs: https://www.business.linkedin.com/advertise/ads/sponsored-content/single-image-ads-specs
- Open Graph protocol: https://ogp.me/

## Practical interpretation
- X: keep the composition comfortably inside a `2:1` frame and prioritize bold headline-safe space.
- X feed: use `16:9` for wide feature posts, `1:1` for portable multi-platform posts, and `4:5` for taller mobile-first product visuals.
- LinkedIn: keep a slightly more editorial `1.91:1` composition with more breathing room and cleaner product framing.
- LinkedIn feed: `1.91:1`, `1:1`, and `1:1.91` are the cleanest working presets for landscape, square, and portrait feed visuals.
- OG: use `1200x630` as the universal default unless a destination platform requires something more specific.

## Source confidence
- The X card preset is based on official X card documentation.
- The LinkedIn landscape, square, and portrait feed presets are aligned to current official LinkedIn single-image specs.
- The X feed landscape/square/portrait presets are **brand-gen working defaults** chosen for practical organic-post composition rather than a single official X organic-feed spec.
- The OG preset is a practical cross-platform default, not a protocol requirement.
