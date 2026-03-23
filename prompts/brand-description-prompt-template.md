# Brand Description Prompt Template

Use this after extracting a brand profile.

Every generation prompt should start from the stored brand guardrail prelude in `brand-identity.json` or `brand-profile.json`.

## Core brand description
```text
[Brand guardrail prelude] Describe the brand in one precise paragraph covering audience, tone, color direction, typography, shape language, and any meaningful design-token cues such as semantic colors, spacing, radius, shadows, or component behaviors.
```

## Browser illustration prompt
```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Preserve the actual interface structure and labels. Borrow only crop, whitespace, browser framing, and background treatment from the chosen presentation references.
```

## Landing hero prompt
```text
Create a full homepage hero, not just a product banner. Include the brand logo, top navigation, headline, subheadline, CTA buttons, branded background, and one real product screenshot as the hero visual. Preserve the real product UI. Do not invent product labels, cards, or features. Use official product-homepage references for layout hierarchy and agency references only for polish.
```

## Product banner prompt
```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Package it into a launch-ready editorial banner using the extracted palette and presentation references only for framing, depth, and polish.
```

## X card prompt
```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Reframe it for a bold 2:1 X card with stronger crop, safe margins, and minimal decorative treatment.
```

## X feed post prompt
```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Choose the right feed preset framing, keep the product instantly readable, and borrow only presentation treatment from the external references.
```

## LinkedIn card prompt
```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Create a cleaner 1.91:1 LinkedIn card with restrained product framing and presentation polish borrowed from the external references.
```

## LinkedIn feed post prompt
```text
Use the real product screenshot as the hero asset. Do not redesign the UI. Keep the layout editorial, readable, and professional, with composition tailored to the chosen preset and presentation references.
```

## Open Graph prompt
```text
Create a universal Open Graph preview image with strong brand identity, product clarity, and link-preview readability.
```

## Feature animation prompt
```text
Create a short branded feature animation with subtle premium motion, smooth reveal timing, and a polished browser/product composition.
```
