#!/usr/bin/env python3
"""Build a reusable brand-identity memory file from a brand profile."""
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


def dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def get_brand_mark(profile: dict) -> dict:
    brand_mark = profile.get('brand_mark')
    if isinstance(brand_mark, dict):
        return brand_mark
    identity = profile.get('identity') or {}
    brand_mark = identity.get('brand_mark')
    if isinstance(brand_mark, dict):
        return brand_mark
    return {}


def get_mark_anatomy(profile: dict) -> list[str]:
    brand_mark = get_brand_mark(profile)
    anatomy = brand_mark.get('anatomy') or brand_mark.get('mark_anatomy') or []
    return dedupe_keep_order([str(item).strip() for item in anatomy if str(item).strip()])


def get_mark_primitives(profile: dict) -> list[str]:
    brand_mark = get_brand_mark(profile)
    primitives = brand_mark.get('approved_primitives') or brand_mark.get('primitives') or []
    return dedupe_keep_order([str(item).strip() for item in primitives if str(item).strip()])


def get_mark_compositions(profile: dict) -> list[str]:
    brand_mark = get_brand_mark(profile)
    comps = brand_mark.get('approved_compositions') or brand_mark.get('compositions') or []
    return dedupe_keep_order([str(item).strip() for item in comps if str(item).strip()])


def get_forbidden_abstractions(profile: dict) -> list[str]:
    brand_mark = get_brand_mark(profile)
    items = brand_mark.get('forbidden_abstractions') or brand_mark.get('banned_abstractions') or []
    return dedupe_keep_order([str(item).strip() for item in items if str(item).strip()])


def derive_non_interface_devices(profile: dict, design_language: dict, design_memory: dict) -> tuple[list[str], list[str]]:
    keywords = {str(item).strip().lower() for item in (profile.get('keywords') or []) if str(item).strip()}
    components = [str(item).strip() for item in (design_language.get('component_cues') or design_memory.get('components') or []) if str(item).strip()]
    mark_anatomy = get_mark_anatomy(profile)
    mark_primitives = get_mark_primitives(profile)
    devices: list[str] = []
    forbidden: list[str] = [
        'invented app names, repo names, or fake navigation rendered as campaign copy',
        'invented product claims, launch slogans, or startup boilerplate written by the image model',
        'random chat bubbles, notifications, or unrelated dashboard chrome in non-interface materials',
        'decorative symbols that are not clearly derived from the logo, product logic, or approved brand motifs',
        'generic neon, glass, sci-fi, or glossy 3D tropes that erase the stored palette and tone',
    ]
    forbidden.extend(get_forbidden_abstractions(profile))
    if profile.get('logo_candidates'):
        devices.append('the stored logo or mark silhouette as the primary symbol')
    if mark_anatomy:
        devices.append(f'exact mark anatomy such as {sentence_join(mark_anatomy[:4])}')
    if mark_primitives:
        devices.append(f'a small approved primitive set such as {sentence_join(mark_primitives[:4])}')
    if keywords & {'network', 'system', 'community', 'governed', 'knowledge', 'curated'}:
        devices.append('interlocking routed-line, lattice, or path motifs derived from the brand mark and system idea')
    if keywords & {'premium', 'editorial', 'calm', 'warm', 'light'}:
        devices.append('quiet editorial fields with generous negative space and warm palette discipline')
    devices.append('one restrained accent field or emblem rather than a collage of unrelated objects')
    if components:
        devices.append(f'edge treatments and geometry that still echo component cues such as {sentence_join(components[:3])}')
    devices.append('at most one proof cue when the material is primarily brand-led rather than product-led')
    return dedupe_keep_order(devices), dedupe_keep_order(forbidden)


def build_material_prompt_snippets(profile: dict, design_language: dict, design_memory: dict) -> dict[str, dict[str, str]]:
    brand_name = profile.get('brand_name') or 'The brand'
    palette = sentence_join((profile.get('color_candidates') or [])[:4]) or 'the stored brand palette'
    typography = sentence_join((profile.get('font_candidates') or [])[:3]) or 'the stored typography system'
    shape = sentence_join((profile.get('radius_tokens') or [])[:3]) or 'the stored shape language'
    components = sentence_join((design_language.get('component_cues') or design_memory.get('components') or [])[:4]) or 'the stored component system'
    layout = sentence_join((design_memory.get('layout') or [])[:3]) or 'quiet whitespace and a single dominant proof surface'
    doctrine = sentence_join((design_memory.get('principles') or [])[:3]) or 'clarity over decoration and one hero product moment'
    motion = sentence_join((design_memory.get('motion') or [])[:3]) or 'restrained motion and gentle reveal timing'
    approved_devices, forbidden_elements = derive_non_interface_devices(profile, design_language, design_memory)
    approved = sentence_join(approved_devices[:4]) or 'the approved brand motifs and mark logic'
    forbidden = sentence_join(forbidden_elements[:4]) or 'invented off-brand UI or campaign tropes'
    mark_anatomy = sentence_join(get_mark_anatomy(profile)[:4]) or 'the exact stored mark anatomy'
    mark_primitives = sentence_join(get_mark_primitives(profile)[:5]) or 'a small approved primitive set derived from the mark'
    mark_compositions = sentence_join(get_mark_compositions(profile)[:4]) or 'one hero mark carrier, one repeat tile, and one border or band variation'

    return {
        'browser_illustration': {
            'default': (
                f"For browser illustrations, keep one real product moment dominant, one inset maximum, and preserve actual UI hierarchy. "
                f"Use {components} as the product language and keep the frame grounded in {palette}, {typography}, and {shape}."
            ),
            'reference': (
                "In reference mode, treat attached screenshots as hard constraints. Crop deeper into the strongest proof surface and improve framing without inventing chrome."
            ),
            'inspiration': (
                f"In inspiration mode, let external references influence crop, whitespace, and atmosphere only. Keep the final interface recognizably {brand_name}."
            ),
            'hybrid': (
                "In hybrid mode, let real product truth lead. Use outside references only to sharpen whitespace, crop discipline, and atmosphere."
            ),
        },
        'landing_hero': {
            'default': (
                f"For landing heroes, build a real homepage hero: brand mark, headline, subheadline, CTA, and one dominant product proof. "
                f"Use {layout} and keep the hero clearly rooted in {brand_name} rather than generic SaaS."
            ),
            'reference': (
                "In reference mode, preserve recognizable brand structure and real product proof while tightening the hero hierarchy."
            ),
            'inspiration': (
                f"In inspiration mode, explore stronger headline/product balance and editorial framing, but do not let reference polish erase {brand_name}'s tone."
            ),
            'hybrid': (
                "In hybrid mode, combine real brand/product anchors with stronger campaign framing from trusted hero references."
            ),
        },
        'product_banner': {
            'default': (
                f"For product banners, stage one key proof moment in a wide atmospheric frame. "
                f"Do not redesign the UI; preserve the stored component language ({components}) and doctrine ({doctrine}) while using {layout}."
            ),
            'reference': (
                f"In reference mode, preserve the supplied product surface and recognizable brand cues, then improve the surrounding field, crop, and focal hierarchy."
            ),
            'inspiration': (
                f"In inspiration mode, push atmosphere, framing, and campaign polish farther, but keep the banner tied to {brand_name}'s palette, typography, and component behavior."
            ),
            'hybrid': (
                f"In hybrid mode, use the real screenshot as truth and reference banners as framing teachers only. "
                f"One proof surface, one atmosphere, no generic dashboard collage."
            ),
        },
        'feature_illustration': {
            'default': (
                f"For feature illustrations, connect one real product moment to the larger brand story. Keep one proof moment clear and the framing grounded in {palette}, {typography}, {shape}, and {components}."
            ),
            'reference': (
                f"In reference mode, preserve the feature's real UI truth and recognizable product sequence. "
                f"Use illustration only to package and clarify, not to rewrite the feature."
            ),
            'inspiration': (
                f"In inspiration mode, widen the visual metaphor and campaign mood, but maintain the brand's doctrine ({doctrine}) and keep the feature story readable."
            ),
            'hybrid': (
                f"In hybrid mode, keep one real feature proof at the center and use external references to guide abstraction level, depth, and branded framing."
            ),
        },
        'styleframe': {
            'default': (
                f"For styleframes, emphasize mood and campaign polish without losing brand identity. "
                f"Use doctrine such as {doctrine}, keep layout restraint from {layout}, and make the brand field feel deliberate, premium, and recognizably {brand_name}. "
                f"Use approved devices such as {approved}, and never introduce {forbidden}."
            ),
            'reference': (
                f"In reference mode, preserve recognizable brand anchors and current palette logic while heightening atmosphere. "
                f"The styleframe should feel like a richer campaign expression of the existing brand, not a new brand."
            ),
            'inspiration': (
                f"In inspiration mode, explore bolder campaign mood, typography tension, and editorial framing, but keep the output anchored in {brand_name}'s actual design language."
            ),
            'hybrid': (
                f"In hybrid mode, use brand truth as the spine and inspiration references for surface confidence, dramatic spacing, and campaign energy."
            ),
        },
        'social': {
            'default': (
                f"For social assets, optimize for mobile readability and instant brand recognition. Use one bold move, one clear message, and keep the visual language anchored in {palette}, {typography}, and {shape}. If copy is needed, compose it deterministically outside the image model."
            ),
            'reference': (
                "In reference mode, preserve recognizable brand/product anchors and tighten the composition for thumbnail readability."
            ),
            'inspiration': (
                f"In inspiration mode, allow a stronger poster-like move, but keep the asset unmistakably within {brand_name}'s palette and typography voice."
            ),
            'hybrid': (
                "In hybrid mode, pair one real product or logo truth anchor with one bold campaign move from references."
            ),
        },
        'feature_animation': {
            'default': (
                f"For feature animation and motion outputs, preserve UI/product truth and animate with {motion}. "
                f"Favor subtle reveals, restrained highlight sweeps, and clean final holds. Do not let motion override brand clarity, palette discipline, or component cues such as {components}."
            ),
            'reference': (
                f"In reference mode, use the supplied stills or product surfaces as animation truth. "
                f"Motion should clarify and elevate what already exists rather than inventing new interface states."
            ),
            'inspiration': (
                f"In inspiration mode, explore more expressive pacing and atmosphere, but keep the animation structurally tied to {brand_name}'s doctrine, palette, and shape language."
            ),
            'hybrid': (
                f"In hybrid mode, animate real product truth with inspiration-led pacing, framing, and mood. "
                f"Preserve brand recognition through every motion beat."
            ),
        },
        'campaign_poster': {
            'default': (
                f"For campaign posters, keep the asset branded before it is decorative. "
                f"Name exact brand anatomy first: {mark_anatomy}. Restrict the poster to {mark_primitives}. "
                f"Use approved graphic devices such as {approved}, keep the field anchored in {palette}, and treat any headline or footer copy as deterministic fixed copy rather than model-invented text. "
                f"Prefer one dominant move plus one support move only: for example one mark carrier, one band or line system, and one text block. "
                f"The output should read like a flat poster composition, not an installation photo, landing page, or moodboard wall. "
                f"Do not introduce {forbidden}."
            ),
            'reference': (
                f"In reference mode, preserve the stored mark, palette, and geometry as hard constraints. "
                f"Poster composition can become bolder, but the brand must remain instantly recognizable at a glance."
            ),
            'inspiration': (
                f"In inspiration mode, push editorial scale, spacing, and campaign confidence, but keep the poster inside {brand_name}'s real identity system rather than drifting into a generic launch poster."
            ),
            'hybrid': (
                f"In hybrid mode, let the real brand mark and palette lead while outside references sharpen pacing, hierarchy, and print-like confidence."
            ),
        },
        'pattern_system': {
            'default': (
                f"For pattern or motif systems, derive repeatable graphic logic from exact mark anatomy: {mark_anatomy}. "
                f"Use only approved primitives such as {mark_primitives}. Build a disciplined system, not an abstract moodboard: one hero tile, one repeat tile, one border or band treatment, and one emblem or carrier variation maximum. "
                f"Choose one system mechanic first—banding, pillar fragments, carrier repetition, or cap-and-stem crops—then express that mechanic across all modules. "
                f"Favor crisp module logic, repeated line weights, reusable spacing, and flat board-style presentation rather than photographed environments or gallery mockups. "
                f"Prioritize system behavior over illustration, and avoid {forbidden}."
            ),
            'reference': (
                f"In reference mode, keep the pattern tightly locked to the mark silhouette and the stored geometry. "
                f"This should look like a reusable identity system, not a one-off artwork or a grid of unrelated rounded shapes."
            ),
            'inspiration': (
                f"In inspiration mode, widen the graphic vocabulary only after naming the concrete module logic. Keep the repeat logic simple enough that it could extend across merch, posters, and motion."
            ),
            'hybrid': (
                f"In hybrid mode, use the real mark and palette as the base module, keep the system within {mark_compositions}, and borrow only rhythm, density, and compositional confidence from outside references."
            ),
        },
        'sticker_family': {
            'default': (
                f"For sticker, icon, or badge families, build a coherent set of reusable brand tokens. "
                f"Start with exact mark anatomy: {mark_anatomy}. Use only approved primitives such as {mark_primitives}. "
                f"Make 6 to 9 items maximum across 2 or 3 silhouette families; each item should feel descended from the logo/mark, the approved motifs ({approved}), and the stored palette. "
                f"Present the set as a clean flat sticker sheet or cutout family, not as a poster, homepage, or packaging mockup. "
                f"No meme stickers, mascots, unrelated symbols, nav bars, body copy, or abstract icons that could belong to any startup."
            ),
            'reference': (
                f"In reference mode, keep the shapes simplified and the family recognizably tied to the source logo. "
                f"Consistency matters more than novelty: repeated line weight, repeated corner logic, and repeated carrier geometry."
            ),
            'inspiration': (
                f"In inspiration mode, allow wider variation in framing, border treatments, and badge geometry, but keep the family within the brand's tone, palette, and mark anatomy."
            ),
            'hybrid': (
                f"In hybrid mode, anchor every sticker or badge in the real mark logic while borrowing only packaging polish from reference sets. Each sticker should still read as belonging to the same family at a glance."
            ),
        },
        'merch_poster': {
            'default': (
                f"For merch or event posters, emphasize brand vibe, print-readiness, and collectible appeal. "
                f"Use {approved}, preserve palette and typography cues, and keep any required event copy deterministic. "
                f"Do not let the poster read like fake SaaS marketing, a landing page section, or a UI mockup."
            ),
            'reference': (
                f"In reference mode, keep the poster tightly bound to the real identity and mark recognition. "
                f"Make it feel wearable, displayable, or event-ready rather than like a product screenshot."
            ),
            'inspiration': (
                f"In inspiration mode, push poster boldness and cultural energy, but preserve the actual brand vibe instead of replacing it with trend-chasing graphics."
            ),
            'hybrid': (
                f"In hybrid mode, let the real brand system govern the poster while references inform energy, print pacing, and composition."
            ),
        },
        'brand_bumper': {
            'default': (
                f"For brand bumpers, stingers, or logo animations, preserve exact mark recognition and palette discipline through every frame. "
                f"Name the mark anatomy first: {mark_anatomy}. Animate one clear reveal or transformation only, keep the camera locked or nearly locked, use a 4 to 6 second beat map with one reveal idea and one final hold, and never add extra symbols, fake text, particle swarms, or generic 3D spins. "
                f"Borrow one reveal attitude only—mask wipe, path trace, band slide, or edge crop—rather than blending several motion styles."
            ),
            'reference': (
                f"In reference mode, use the supplied logo or brand frame as hard truth. "
                f"Motion may enhance the reveal, but it must not redraw the identity into something else. Preserve edge fidelity and keep the end frame identical to the source mark."
            ),
            'inspiration': (
                f"In inspiration mode, explore pacing, lighting, and editorial reveal confidence, but keep the bumper unmistakably tied to {brand_name}'s actual mark and brand mood. Borrow one motion attitude from references, not several."
            ),
            'hybrid': (
                f"In hybrid mode, keep the true mark and palette fixed while borrowing only motion pacing and presentation confidence from references. The motion should feel like an established identity sting, not a generic AI logo reveal."
            ),
        },
    }


def build_identity(profile: dict) -> dict:
    brand_name = profile.get('brand_name') or 'The brand'
    description = profile.get('description') or 'a modern digital product'
    keywords = profile.get('keywords') or []
    colors = profile.get('color_candidates') or []
    fonts = profile.get('font_candidates') or []
    radius = profile.get('radius_tokens') or []
    logos = profile.get('logo_candidates') or []
    brand_assets = profile.get('brand_assets') or {}
    design_language = profile.get('design_language') or {}
    tokens = profile.get('design_tokens') or {}
    design_memory = profile.get('design_memory') or {}
    approved_devices, forbidden_elements = derive_non_interface_devices(profile, design_language, design_memory)
    material_prompt_snippets = build_material_prompt_snippets(profile, design_language, design_memory)
    mark_anatomy = get_mark_anatomy(profile)
    mark_primitives = get_mark_primitives(profile)
    mark_compositions = get_mark_compositions(profile)
    prompt_prelude = (
        f'Preserve the brand truth of {brand_name}. '
        f'The brand should feel {sentence_join(keywords[:5]) or "clear, confident, and specific"}. '
        f'Keep palette direction anchored in {sentence_join(colors[:5]) or "its existing palette"}, '
        f'typography cues anchored in {sentence_join(fonts[:3]) or "its existing typography"}, '
        f'and shape language anchored in {sentence_join(radius[:3]) or "its existing interface geometry"}. '
        f'External references may improve framing, crop, and atmosphere, but must not replace the brand identity.'
    )
    interface_prompt_prelude = (
        f"For interface and product-led materials, preserve the real {brand_name} product structure, hierarchy, labels, and workflow proof. "
        f"Keep one hero product moment dominant, avoid synthetic navigation or fake dashboard chrome, and let references influence composition rather than product structure."
    )
    non_interface_rule = (
        f"For non-interface materials, preserve approved brand devices such as {sentence_join(approved_devices[:4]) or 'the approved mark, motifs, palette, and geometry'} before adding mood or references. "
        f"If text is required, compose it deterministically outside the image model. "
        f"Never introduce {sentence_join(forbidden_elements[:4]) or 'invented off-brand campaign or UI elements'}."
    )
    non_interface_prompt_prelude = non_interface_rule
    if mark_anatomy:
        non_interface_prompt_prelude = non_interface_prompt_prelude.rstrip() + ' ' + f"Preserve exact mark anatomy such as {sentence_join(mark_anatomy[:4])}."
    if mark_primitives:
        non_interface_prompt_prelude = non_interface_prompt_prelude.rstrip() + ' ' + f"Use only approved primitives such as {sentence_join(mark_primitives[:5])} when generating brand-led stills."
    if mark_compositions:
        non_interface_prompt_prelude = non_interface_prompt_prelude.rstrip() + ' ' + f"Prefer approved composition patterns such as {sentence_join(mark_compositions[:4])}."
    if design_memory.get('principles') or design_memory.get('components') or design_memory.get('layout'):
        if design_memory.get('principles'):
            principle_text = sentence_join((design_memory.get('principles') or [])[:3])
            prompt_prelude = prompt_prelude.rstrip() + ' ' + f"Honor extracted doctrine such as {principle_text}."
        if design_memory.get('components') or design_memory.get('layout'):
            additions = []
            if design_memory.get('components'):
                additions.append(f"preserve component cues such as {sentence_join((design_memory.get('components') or [])[:3])}")
            if design_memory.get('layout'):
                additions.append(f"keep layout discipline aligned with {sentence_join((design_memory.get('layout') or [])[:2])}")
            interface_prompt_prelude = interface_prompt_prelude.rstrip() + ' ' + '. '.join(additions).strip() + '.'

    return {
        'schema_version': 1,
        'brand': {
            'name': brand_name,
            'summary': description,
            'homepage_url': profile.get('homepage_url') or '',
            'project_root': profile.get('project_root') or '',
        },
        'identity_core': {
            'tone_words': keywords[:10],
            'brand_anchors': logos[:10],
            'mark_anatomy': mark_anatomy[:10],
            'approved_primitives': mark_primitives[:10],
            'approved_compositions': mark_compositions[:10],
            'must_preserve': {
                'palette_direction': colors[:10],
                'typography_cues': fonts[:10],
                'shape_language': radius[:10],
            },
            'brand_truth_rules': [
                profile.get('identity', {}).get('presentation_rule') or 'Presentation references may influence composition, not identity.',
                profile.get('identity', {}).get('product_truth_rule') or 'Product truth stays faithful unless explicit redesign is requested.',
                profile.get('identity', {}).get('design_memory_rule') or 'Parsed design-memory doctrine should reinforce brand truth instead of replacing it.',
                'Brand materials should maintain the aesthetic and vibe of the brand before borrowing outside framing ideas.',
                'Do not synthesize fake lockups or fake wordmarks; only use stored brand assets that actually exist.',
            ],
            'approved_graphic_devices': approved_devices[:10],
            'forbidden_elements': forbidden_elements[:10],
        },
        'brand_assets': brand_assets,
        'design_language': design_language,
        'design_tokens': tokens,
        'design_memory': design_memory,
        'generation_guardrails': {
            'prompt_prelude': prompt_prelude,
            'interface_prompt_prelude': interface_prompt_prelude,
            'non_interface_prompt_prelude': non_interface_prompt_prelude,
            'reference_rule': 'External references control framing, crop, and campaign treatment. They do not override brand tone, palette, typography, shape language, or design tokens.',
            'inspiration_translation_rule': 'Translate inspiration into mechanics only. Borrow composition, system logic, application attitude, or motion pacing from references, but keep logo, typography, copy, product truth, and mark logic owned by the stored brand.',
            'material_separation_rule': 'Different material types must remain visually distinct instead of collapsing into the same layout skeleton.',
            'identity_rule': 'If a generated artifact feels generic or unbranded, strengthen brand cues before adding more presentation styling.',
            'design_memory_rule': 'When parsed design-memory exists, use its doctrine, layout discipline, and component cues to strengthen the brand system before borrowing presentation references.',
            'non_interface_rule': non_interface_rule,
            'copy_rule': 'For campaign posters, merch, badges, and other non-interface materials, use zero text inside the image model unless the copy is composed deterministically outside the model.',
            'asset_rule': 'Never invent a synthetic lockup by typesetting the brand name next to the icon. Use only stored icon, wordmark, or lockup assets; if only an icon exists, show only the icon.',
            'material_prompt_snippets': material_prompt_snippets,
        },
        'material_set_templates': {
            'product_core': {
                'description': 'Default product-led set: hero, product proof, social proof, motion proof, and one supporting identity system.',
                'materials': ['landing-hero', 'browser-illustration', 'x-feed', 'feature-animation', 'pattern-system'],
            },
            'launch_core': {
                'description': 'Launch-ready set balancing product proof and campaign surfaces.',
                'materials': ['landing-hero', 'feature-illustration', 'x-feed', 'bumper-animation', 'pattern-system'],
            },
            'brand_system_core': {
                'description': 'System-first set for brands that already have strong product proof and want applied identity extensions.',
                'materials': ['campaign-poster', 'pattern-system', 'sticker-family', 'bumper-animation'],
            },
        },
        'material_dna': {
            'browser_illustration': 'Faithful product section visual with quiet brand field and readable UI.',
            'product_banner': 'Wide atmospheric support visual that preserves brand tone while staging one key product proof moment.',
            'feature_illustration': 'Concept-led proof visual that connects one product moment to the brand\'s larger system or story.',
            'styleframe': 'Motion-ready campaign still with a stronger brand field, stronger mood, and less generic screenshot packaging.',
            'social': 'Poster-first branded social asset that stays readable on mobile and carries the brand vibe clearly at thumbnail size.',
            'campaign_poster': 'Deterministic or fixed-copy poster that keeps the brand mark, palette, and motifs more important than invented campaign text.',
            'pattern_system': 'Reusable tile, path, or band logic derived from the mark and palette rather than one-off illustration.',
            'sticker_family': 'A coherent family of icons, stickers, or badges that all clearly descend from the mark and approved motifs.',
            'merch_poster': 'A poster or merch-facing artifact that feels collectible and print-ready without losing the source brand.',
            'brand_bumper': 'A short motion bumper or stinger that preserves exact logo recognition while adding a restrained reveal.',
        },
    }


def to_markdown(identity: dict) -> str:
    brand = identity['brand']
    core = identity['identity_core']
    lines = [
        f"# {brand['name']} brand identity",
        '',
        '## Brand overview',
        f"- Summary: {brand['summary'] or 'n/a'}",
        f"- Homepage: {brand['homepage_url'] or 'n/a'}",
        f"- Project root: {brand['project_root'] or 'n/a'}",
        '',
        '## Tone and anchors',
        f"- Tone words: {sentence_join(core.get('tone_words', [])) or 'n/a'}",
        f"- Brand anchors: {sentence_join(core.get('brand_anchors', [])) or 'n/a'}",
        f"- Brand assets: icon={((identity.get('brand_assets') or {}).get('icon') or 'n/a')}, wordmark={((identity.get('brand_assets') or {}).get('wordmark') or 'n/a')}, lockup={((identity.get('brand_assets') or {}).get('lockup') or 'n/a')}",
        '',
        '## Must preserve',
        f"- Palette direction: {sentence_join(core.get('must_preserve', {}).get('palette_direction', [])) or 'n/a'}",
        f"- Typography cues: {sentence_join(core.get('must_preserve', {}).get('typography_cues', [])) or 'n/a'}",
        f"- Shape language: {sentence_join(core.get('must_preserve', {}).get('shape_language', [])) or 'n/a'}",
        f"- Mark anatomy: {sentence_join(core.get('mark_anatomy', [])) or 'n/a'}",
        f"- Approved primitives: {sentence_join(core.get('approved_primitives', [])) or 'n/a'}",
        f"- Approved compositions: {sentence_join(core.get('approved_compositions', [])) or 'n/a'}",
        f"- Approved graphic devices: {sentence_join(core.get('approved_graphic_devices', [])) or 'n/a'}",
        f"- Forbidden elements: {sentence_join(core.get('forbidden_elements', [])) or 'n/a'}",
        '',
        '## Design language',
        f"- Semantic palette roles: {sentence_join(identity.get('design_language', {}).get('semantic_palette_roles', [])) or 'n/a'}",
        f"- Typography voice: {sentence_join(identity.get('design_language', {}).get('typography_voice', [])) or 'n/a'}",
        f"- Component cues: {sentence_join(identity.get('design_language', {}).get('component_cues', [])) or 'n/a'}",
        f"- Framework cues: {sentence_join(identity.get('design_language', {}).get('framework_cues', [])) or 'n/a'}",
        '',
        '## Global prompt prelude',
        '```text',
        identity.get('generation_guardrails', {}).get('prompt_prelude', ''),
        '```',
        '',
        '## Non-interface rules',
        f"- Non-interface rule: {(identity.get('generation_guardrails', {}) or {}).get('non_interface_rule') or 'n/a'}",
        f"- Copy rule: {(identity.get('generation_guardrails', {}) or {}).get('copy_rule') or 'n/a'}",
        '',
        '## Guardrails',
    ]
    for item in identity.get('generation_guardrails', {}).values():
        if isinstance(item, str) and item and item != identity.get('generation_guardrails', {}).get('prompt_prelude', ''):
            lines.append(f'- {item}')
    templates = identity.get('material_set_templates') or {}
    if templates:
        lines += ['', '## Material set templates']
        for key, value in templates.items():
            lines.append(f"- **{key}**: {value.get('description', 'n/a')}")
            mats = value.get('materials') or []
            if mats:
                lines.append(f"  - materials: {sentence_join(mats)}")
    lines += ['', '## Material DNA']
    for key, value in identity.get('material_dna', {}).items():
        lines.append(f'- **{key}**: {value}')
    snippets = identity.get('generation_guardrails', {}).get('material_prompt_snippets') or {}
    if snippets:
        lines += ['', '## Material-specific prompt snippets']
        for key, value in snippets.items():
            if isinstance(value, dict):
                lines.append(f'- **{key}**')
                for mode_key, mode_value in value.items():
                    lines.append(f'  - `{mode_key}`: {mode_value}')
            else:
                lines.append(f'- **{key}**: {value}')
    tokens = identity.get('design_tokens') or {}
    if tokens:
        lines += [
            '', '## Imported design tokens snapshot',
            f"- Source file: {tokens.get('source_file', 'n/a')}",
            f"- Source URL: {tokens.get('source_url', 'n/a') or 'n/a'}",
            f"- Typography styles: {len(tokens.get('typography', {}).get('styles', []))}",
            f"- Spacing values: {len(tokens.get('spacing', {}).get('common_values', []))}",
            f"- Component groups: {sentence_join(list((tokens.get('components') or {}).keys())) or 'n/a'}",
        ]
    design_memory = identity.get('design_memory') or {}
    if design_memory:
        lines += [
            '', '## Parsed design-memory snapshot',
            f"- Source dir: {design_memory.get('source_dir', 'n/a') or 'n/a'}",
            f"- Files present: {sentence_join(design_memory.get('files_present', [])) or 'n/a'}",
            f"- Principles: {sentence_join(design_memory.get('principles', [])[:6]) or 'n/a'}",
            f"- Components: {sentence_join(design_memory.get('components', [])[:6]) or 'n/a'}",
            f"- Layout cues: {sentence_join(design_memory.get('layout', [])[:6]) or 'n/a'}",
            f"- Motion cues: {sentence_join(design_memory.get('motion', [])[:6]) or 'n/a'}",
            f"- CSS variables: {len(design_memory.get('css_variables', {}))}",
        ]
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Build a reusable brand identity memory file from a brand profile')
    parser.add_argument('--profile', required=True, help='Path to brand-profile.json')
    parser.add_argument('--output-json', required=True, help='Output identity JSON path')
    parser.add_argument('--output-markdown', required=True, help='Output identity markdown path')
    args = parser.parse_args()

    profile = json.loads(Path(args.profile).expanduser().resolve().read_text())
    identity = build_identity(profile)
    output_json = Path(args.output_json).expanduser().resolve()
    output_markdown = Path(args.output_markdown).expanduser().resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(identity, indent=2) + '\n')
    output_markdown.write_text(to_markdown(identity))
    print(f'Brand identity JSON: {output_json}')
    print(f'Brand identity markdown: {output_markdown}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
