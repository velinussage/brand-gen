# Style

:root {
  --ref-visual-density: airy;
  --ref-product-proof-emphasis: high;
  --ref-shape-language: rounded;
  --ref-hierarchy-mode: editorial;
  --ref-accent-handling: restrained;
  --tw-content: "";
  --breakpoint: "xs";
  --container-width: unset;
  --inner-gutter: 12px;
  --outer-gutter: 12px;
  --grid-columns: 6;
  --env: "production";
  --grid-column-bg: rgba(127, 255, 255, .25);
  --breakpoint: "sm";
  --grid-columns: 12;
  --breakpoint: "md";
  --outer-gutter: 16px;
  --breakpoint: "lg";
  --outer-gutter: 24px;
  --breakpoint: "xl";
  --container-width: 1792px;
  --inner-gutter: 16px;
  --outer-gutter: 32px;
  --breakpoint: "xxl";
  --container-outer-gutter: 0;
  --breakout-container-outer-gutter: 0;
  --breakout-outer-gutter: max(var(--outer-gutter), calc((100% - var(--container-width, 100%)) / 2));
  --breakout-container-outer-gutter: var(--outer-gutter);
  --scrollbar-bg: #fafafa;
}

## Color palette
- Neutral-led palette with restrained chroma.
- Strong dark/light contrast carries the hierarchy.
- One restrained accent should carry emphasis rather than many competing tones.

## Typography
- Observed type families include ui-sans-serif, ui-monospace.
- Type should carry hierarchy through scale contrast and restrained support copy.
