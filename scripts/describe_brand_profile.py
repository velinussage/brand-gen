#!/usr/bin/env python3
"""Generate reusable brand description prompts from an extracted brand profile / identity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def sentence_join(items: list[str]) -> str:
    items = [str(item).strip() for item in items if str(item).strip()]
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f'{items[0]} and {items[1]}'
    return ', '.join(items[:-1]) + f', and {items[-1]}'


def load_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def prefix_prompt(prelude: str, body: str) -> str:
    prelude = (prelude or '').strip()
    body = (body or '').strip()
    if prelude and body:
        return f'{prelude} {body}'
    return prelude or body


def main() -> int:
    parser = argparse.ArgumentParser(description='Describe a brand profile and generate prompt blocks.')
    parser.add_argument('--profile', required=True, help='Path to brand profile JSON')
    parser.add_argument('--output', required=True, help='Output markdown path')
    parser.add_argument('--identity', help='Optional brand-identity.json path; defaults to sibling file if present')
    parser.add_argument('--voice', help='Optional voice/tone override')
    parser.add_argument('--audience', help='Optional audience override')
    args = parser.parse_args()

    profile_path = Path(args.profile).expanduser().resolve()
    profile = load_json(profile_path)
    identity_path = Path(args.identity).expanduser().resolve() if args.identity else profile_path.with_name('brand-identity.json')
    identity = load_json(identity_path)

    brand_name = profile.get('brand_name') or identity.get('brand', {}).get('name') or 'The brand'
    description = profile.get('description') or identity.get('brand', {}).get('summary') or 'a modern digital product'
    colors = profile.get('color_candidates') or identity.get('identity_core', {}).get('must_preserve', {}).get('palette_direction') or []
    fonts = profile.get('font_candidates') or identity.get('identity_core', {}).get('must_preserve', {}).get('typography_cues') or []
    keywords = profile.get('keywords') or identity.get('identity_core', {}).get('tone_words') or []
    radius = profile.get('radius_tokens') or identity.get('identity_core', {}).get('must_preserve', {}).get('shape_language') or []
    logos = profile.get('logo_candidates') or identity.get('identity_core', {}).get('brand_anchors') or []
    homepage = profile.get('homepage_url') or identity.get('brand', {}).get('homepage_url') or 'n/a'
    voice = args.voice or sentence_join(keywords[:4]) or 'modern, confident, clear'
    audience = args.audience or 'product-minded users who care about clarity, taste, and usability'
    color_text = sentence_join(colors[:6]) or 'a restrained palette'
    font_text = sentence_join(fonts[:4]) or 'clean contemporary typography'
    shape_text = sentence_join(radius[:4]) or 'clean rounded geometry'
    logo_text = sentence_join(logos[:3]) or 'existing product marks'
    guardrail_prelude = (
        identity.get('generation_guardrails', {}).get('prompt_prelude')
        or profile.get('brand_guardrail_prelude')
        or profile.get('identity', {}).get('brand_guardrail_prelude')
        or ''
    )
    design_language = profile.get('design_language') or identity.get('design_language') or {}
    design_memory = profile.get('design_memory') or identity.get('design_memory') or {}
    component_cues = sentence_join(design_language.get('component_cues', [])[:6]) or 'the existing component system'
    semantic_roles = sentence_join(design_language.get('semantic_palette_roles', [])[:6]) or 'existing semantic color roles'
    doctrine_text = sentence_join((design_memory.get('principles') or [])[:3]) or 'the stored design doctrine'
    layout_text = sentence_join((design_memory.get('layout') or [])[:3]) or 'the stored layout discipline'
    motion_text = sentence_join((design_memory.get('motion') or [])[:3]) or 'restrained motion cues'

    core_description = (
        f"{brand_name} should feel {voice}. It is presented as {description}. "
        f"The audience is {audience}. The visual system should draw from {color_text}, "
        f"use {font_text}, preserve cues from {logo_text}, keep shape language aligned with {shape_text}, "
        f"and stay consistent with doctrine such as {doctrine_text} and layout cues such as {layout_text}."
    )

    lines = [
        f'# {brand_name} brand description prompts',
        '',
        '## Extracted profile summary',
        f'- Homepage: {homepage}',
        f'- Description: {description}',
        f'- Keywords: {sentence_join(keywords[:8]) or "n/a"}',
        f'- Colors: {sentence_join(colors[:8]) or "n/a"}',
        f'- Fonts: {sentence_join(fonts[:8]) or "n/a"}',
        f'- Shape hints: {sentence_join(radius[:6]) or "n/a"}',
        f'- Component cues: {component_cues}',
        f'- Semantic roles: {semantic_roles}',
        f'- Design-memory doctrine: {doctrine_text}',
        f'- Layout cues: {layout_text}',
        f'- Motion cues: {motion_text}',
        '',
        '## Global brand guardrail prelude',
        '```text',
        guardrail_prelude,
        '```',
        '',
        '## Core brand description',
        '```text',
        core_description,
        '```',
        '',
        '## Visual system prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Describe the {brand_name} visual system in a way that a designer or image model can use. Emphasize {voice}, a palette built around {color_text}, typography inspired by {font_text}, shape language informed by {shape_text}, and component cues from {component_cues}. Keep the output specific, modern, and operational rather than abstract.'),
        '```',
        '',
        '## Browser illustration prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Use the real {brand_name} product screenshot as the hero asset. Do not redesign the UI. Preserve the actual interface structure and labels. Borrow only crop discipline, whitespace, browser framing, and background treatment from the chosen presentation references. Keep the result aligned with {voice}, palette cues from {color_text}, typography inspired by {font_text}, shape language from {shape_text}, and doctrine such as {doctrine_text}.'),
        '```',
        '',
        '## Landing hero prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Create a full homepage hero for {brand_name}, not just a product banner. Include the logo, top navigation, headline, subheadline, CTA buttons, branded background, and one real product screenshot as the hero visual. Preserve the actual UI and use official product-homepage references for text-to-product balance, then use agency references only for polish. Keep the result aligned with {voice}, {color_text}, {font_text}, the stored component system, and layout discipline such as {layout_text}.'),
        '```',
        '',
        '## Product banner prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Use the real {brand_name} product screenshot as the hero asset. Do not redesign the UI. Package one key product moment into a launch-ready banner using {color_text} as the main palette, {font_text} as the typographic direction, and presentation references only for framing, depth, and polish.'),
        '```',
        '',
        '## X card prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Generate a 2:1 X card for {brand_name} using the real product screenshot as the hero asset. Do not redesign the UI. Reframe it with a stronger crop, safe margins, and a brand-forward layout based on {color_text}, {font_text}, and the overall tone {voice}.'),
        '```',
        '',
        '## X feed prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Generate an X feed post for {brand_name} using the real product screenshot as the hero asset. Do not redesign the UI. Choose framing that fits the intended preset, keep the product instantly readable on mobile, and borrow only presentation treatment from the external references while staying aligned with {color_text}, {font_text}, and the overall tone {voice}.'),
        '```',
        '',
        '## LinkedIn card prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Generate a 1.91:1 LinkedIn card for {brand_name} using the real product screenshot as the hero asset. Do not redesign the UI. Use a cleaner, more editorial and professional composition than the X version, with restrained brand color usage and presentation polish borrowed from the external references.'),
        '```',
        '',
        '## LinkedIn feed prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Generate a LinkedIn feed post for {brand_name} using the real product screenshot as the hero asset. Do not redesign the UI. Choose framing that fits the intended preset, keep the hierarchy editorial and professional, and borrow only whitespace, framing, and polish from the external references while staying aligned with {color_text}, {font_text}, and the overall tone {voice}.'),
        '```',
        '',
        '## Open Graph prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Generate a universal Open Graph preview image for {brand_name}. It should communicate the product and brand instantly using {color_text}, {font_text}, and a strong hierarchy between product visual, headline area, and brand identity.'),
        '```',
        '',
        '## Feature animation prompt',
        '```text',
        prefix_prompt(guardrail_prelude, f'Create a short branded feature animation for {brand_name}. Animate an illustrated browser or interface moment with subtle premium motion, smooth reveal timing, and restrained camera movement. Keep the motion aligned with {voice}, avoid chaotic distortion, preserve a clean branded composition using {color_text}, and borrow motion cues such as {motion_text}.'),
        '```',
    ]

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n')
    print(f'Brand description prompts: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
