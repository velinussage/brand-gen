# Brand Identity Memory

Use this after extracting a brand profile and before generating any brand material.

## Goal
Store the full brand identity and design language so generation stays branded rather than merely well-presented.

## Brand truth comes first
Every prompt should preserve, in order:
1. brand tone / vibe
2. palette direction
3. typography cues
4. shape language
5. component behavior
6. product truth

Presentation references can influence framing and campaign treatment, but they must not replace those six layers.

## Non-interface brand rule
When the asset is not a product interface:
- preserve approved brand devices first: mark/logo silhouette, palette logic, typography cues, and system motifs derived from the brand
- do **not** let the model invent app names, fake product claims, fake chat bubbles, or generic startup campaign copy
- if text is required, compose it deterministically outside the image model
- one symbolic/system move beats five unrelated decorative moves

## What to store
- brand summary
- tone words
- recognizable anchors
- palette direction
- semantic color roles
- typography families and style cues
- shape language and border-radius tendencies
- spacing scale
- shadow / depth behavior
- component cues
- framework / icon-system cues when useful
- global prompt prelude / brand guardrail text

## Core rule
If an output is polished but feels unbranded, strengthen the stored brand identity before trying more examples.
