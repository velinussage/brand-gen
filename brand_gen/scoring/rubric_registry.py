"""Rubric registry — source of truth for the v2 scoring rubric.

Inline Python dict. Editable without touching any other file.
`to_markdown()` regenerates the critic agent prose from this registry.
`to_json_dict()` serializes for `bgen show-rubric --format json` and
for any downstream consumer (scorer, eval harness, PR comment bots).

v1 covers landing-hero plus a small set of SaaS illustration / poster / pattern
materials explicitly. Other materials fall through to universal axes only.

To add a material overlay: extend MATERIAL_OVERLAYS with a dict.
To add a universal axis: extend UNIVERSAL_AXES (affects every run — do this
with intent and coordinate with the critic agent prose update).
"""
from __future__ import annotations

from typing import Any


RUBRIC_VERSION = "2026-04-22"


UNIVERSAL_AXES: list[dict[str, str]] = [
    {
        "name": "composition",
        "definition": (
            "Layout hierarchy, focal point, whitespace balance. Does the eye land where "
            "the designer intended? Does negative space work as a first-class element or "
            "does the composition feel cluttered? Is there ONE dominant gesture plus a "
            "support system, or competing focal points?"
        ),
    },
    {
        "name": "brand_coherence",
        "definition": (
            "Palette accuracy vs. brand-identity.json, approved devices only, mark usage "
            "follows the identity rules, typography matches the brand's declared fonts "
            "with appropriate fallbacks. An output that looks premium but uses the wrong "
            "palette or invents a device scores low regardless of taste."
        ),
    },
    {
        "name": "restraint",
        "definition": (
            "Absence of generic premium-AI decoration: no glassmorphism, no purple/violet "
            "gradients, no neon-on-dark, no 3-column icon grids with colored circles, no "
            "invented gibberish text, no duplicate brand marks. The output earns its "
            "polish through material choice and proportion, not through effects."
        ),
    },
    {
        "name": "story_fidelity",
        "definition": (
            "Does this tell the intended story for this specific surface? Given the "
            "plan's goal and target surface, a reader sees the right message — not a "
            "generic restatement. Story_fidelity measures whether the composition serves "
            "the stated brief, not whether the composition is beautiful."
        ),
    },
    {
        "name": "meaning_clarity",
        "definition": (
            "Would a new visitor understand what this is about in 2–3 seconds? "
            "Meaning_clarity is what separates 'tasteful but meaningless' from 'tasteful "
            "and legible.' It does NOT mean explicit text labels — a strong symbolic "
            "image can have high meaning_clarity if the symbol is decoded fast. It DOES "
            "mean generic aesthetic choices that could belong to any brand score low."
        ),
    },
]


MATERIAL_OVERLAYS: dict[str, dict[str, Any]] = {
    "landing-hero": {
        "material_rubric_key": "landing-hero",
        "overlay_axes": [
            {
                "name": "surface_fit",
                "definition": (
                    "Does the composition respect landing-hero conventions? Left-column "
                    "copy supported by right-column art, or full-bleed with headline "
                    "overlay that reads cleanly. Screenshot treatment (if any) is "
                    "intentional art direction, not an inset proof panel. The hero does "
                    "not read as a social card or an ad."
                ),
            },
            {
                "name": "meaning_at_glance",
                "definition": (
                    "In 2–3 seconds, does a visitor understand what product category "
                    "this is in? Landing heroes that need a paragraph to decode score "
                    "low. The image does most of the work; the headline seals it."
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "landing-hero-no-product-category",
            "description": (
                "The hero does not communicate a product category. A visitor lands, "
                "looks at the hero, and cannot say 'this is an X tool / X platform / "
                "X product' within 3 seconds. Generic 'premium AI brand' art without "
                "a specific product reference triggers this rule."
            ),
            "detection_prompt": (
                "Look at this image as if you have never heard of the brand. Can you "
                "name, within 3 seconds, the product category it belongs to? Examples "
                "of sufficient categories: 'developer tool', 'design platform', 'AI "
                "orchestration framework', 'payments infrastructure', 'team "
                "collaboration tool'. If you cannot name a category — if the best you "
                "can say is 'some premium tech brand' or 'some AI thing' — the "
                "disqualifier is triggered. Return true if triggered, false otherwise."
            ),
        },
    },
    "concept-illustration": {
        "material_rubric_key": "concept-illustration",
        "overlay_axes": [
            {
                "name": "system_logic_visible",
                "definition": (
                    "Is there a visible system at work — composition that implies a "
                    "process, relationship, or mechanism — or is this just decorative "
                    "icon worship? Concept illustrations that show a visual system "
                    "(nodes + edges, strata + flow, parts + whole) earn trust. "
                    "Concept illustrations that show one large symbol floating in "
                    "space without context score low."
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Could a generic premium AI brand have produced this, or is there "
                    "something recognizably specific to THIS brand's visual language, "
                    "metaphor vocabulary, or material palette? Brand-specificity "
                    "rejects interchangeable 'AI brand art'."
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "concept-illustration-generic-abstract-metaphor",
            "description": (
                "The illustration is a generic abstract metaphor (floating cubes, "
                "glowing nodes, gradient orbs, faceless figures in a lit room) with "
                "no connection to the brand's declared philosophy or vocabulary."
            ),
            "detection_prompt": (
                "Examine the illustration. Does it contain specific, named imagery "
                "tied to the brand's design-philosophy.md or custom-scratchpad.md "
                "vocabulary (e.g., rammed-earth textures, library stacks, pattern "
                "systems, specific architectural references)? Or is it generic "
                "abstract imagery (floating geometric shapes, glowing networks, "
                "gradient blobs, silhouetted figures) that could illustrate any AI "
                "or tech brand? If it is generic abstract metaphor with no brand-"
                "specific anchor, return true. Otherwise return false."
            ),
        },
    },
    "system-explainer-illustration": {
        "material_rubric_key": "system-explainer-illustration",
        "overlay_axes": [
            {
                "name": "system_logic_visible",
                "definition": (
                    "Can a viewer see one explicit mechanism, flow, or causal structure "
                    "at work? System explainers should make the product or protocol "
                    "logic feel legible, not merely atmospheric."
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Does the explainer still feel uniquely tied to this brand's visual "
                    "language, metaphor vocabulary, and material palette rather than a "
                    "generic premium SaaS diagram?"
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "system-explainer-illustration-no-mechanism",
            "description": (
                "The image claims to explain a system but shows only atmospheric or "
                "decorative symbolism with no visible mechanism, flow, or structure."
            ),
            "detection_prompt": (
                "Examine the illustration. Could a new viewer point to one specific "
                "system or process in motion (routing, gating, proving, indexing, "
                "selection, transformation)? If not — if it reads as decorative brand "
                "art rather than a system explainer — return true. Otherwise return false."
            ),
        },
    },
    "editorial-metaphor-illustration": {
        "material_rubric_key": "editorial-metaphor-illustration",
        "overlay_axes": [
            {
                "name": "metaphor_clarity",
                "definition": (
                    "Is there one clear metaphor carrying the image, or does it feel like "
                    "a collage of symbols, props, and mood cues? Editorial metaphor "
                    "illustrations should be singular and legible, not encyclopedic."
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Could this metaphor belong only to this brand's declared vocabulary, "
                    "or could any tasteful AI brand have used it?"
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "editorial-metaphor-illustration-collage-no-single-metaphor",
            "description": (
                "The illustration is a collage of symbols or ambience with no single "
                "metaphor doing the communicative work."
            ),
            "detection_prompt": (
                "Examine the illustration. Can you summarize its main metaphor in one "
                "sentence without listing multiple unrelated symbols? If no — if it "
                "reads as a decorative collage or ambient world rather than one clear "
                "editorial metaphor — return true. Otherwise return false."
            ),
        },
    },
    "illustrated-brand-world": {
        "material_rubric_key": "illustrated-brand-world",
        "overlay_axes": [
            {
                "name": "process_implied",
                "definition": (
                    "Does the environment imply the brand's actual process or work, or "
                    "is it just a tasteful architectural / interior mood piece? The "
                    "world should still feel inhabited by the brand's work."
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Does the world carry the brand's declared material vocabulary, mark "
                    "logic, and narrative environment rather than generic premium mood?"
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "illustrated-brand-world-pure-mood-no-process",
            "description": (
                "The world is pure architectural or atmospheric mood with no process, "
                "activity, or evidence that the brand's work happens there."
            ),
            "detection_prompt": (
                "Examine the world. Can you point to specific visual evidence that the "
                "brand's work happens in this environment? If it is only mood, interior, "
                "or cinematic atmosphere with no process implication, return true. "
                "Otherwise return false."
            ),
        },
    },
    "proof-poster": {
        "material_rubric_key": "proof-poster",
        "overlay_axes": [
            {
                "name": "information_hierarchy",
                "definition": (
                    "Is the hierarchy led by the proof payload — quote, screenshot, stat, "
                    "or claim — with the mark supporting it? If the logo is the biggest "
                    "thing and the message is secondary, the poster scores low."
                ),
            },
            {
                "name": "proof_payload_visible",
                "definition": (
                    "Is there an actual payload carrying meaning: visible quote, real "
                    "screenshot, stat, or proof module? Proof posters without a proof "
                    "payload collapse into generic brand ads."
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "proof-poster-logo-dominant-no-proof",
            "description": (
                "The poster is dominated by the brand mark with no clear quote, proof, "
                "or screenshot payload doing the communicative work."
            ),
            "detection_prompt": (
                "Examine the poster. Is the largest or dominant element simply the brand "
                "mark or a logo carrier, while the quote, screenshot, or proof payload is "
                "missing or visibly subordinate? If yes, return true. Otherwise return false."
            ),
        },
    },
    "site-pattern-tile": {
        "material_rubric_key": "site-pattern-tile",
        "overlay_axes": [
            {
                "name": "deployability",
                "definition": (
                    "Does this read like one repeatable, low-contrast tile that could sit "
                    "behind UI on a real site, or like a presentation board / poster / "
                    "motif collage?"
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Is the repeat logic clearly derived from this brand's mark anatomy or "
                    "system language, not a generic abstract wallpaper?"
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "site-pattern-tile-board-not-tile",
            "description": (
                "The output is a board of multiple treatments or a motif collage instead "
                "of one deployable repeatable tile."
            ),
            "detection_prompt": (
                "Examine the pattern output. Does it show one repeatable, low-contrast tile "
                "that could actually be deployed on a website? If instead it shows multiple "
                "competing treatments, presentation framing, or a collage of motifs, return "
                "true. Otherwise return false."
            ),
        },
    },
    "pattern-board": {
        "material_rubric_key": "pattern-board",
        "overlay_axes": [
            {
                "name": "system_coherence",
                "definition": (
                    "Do the explored modules all belong to one repeat grammar, or does the "
                    "board feel like unrelated motifs collected together?"
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Are the board's pattern moves clearly derived from this brand's mark "
                    "anatomy and system logic rather than generic geometric exercises?"
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "pattern-board-unrelated-motif-collage",
            "description": (
                "The board mixes unrelated motifs without a single coherent repeat grammar."
            ),
            "detection_prompt": (
                "Examine the board. Do the modules feel like variations inside one system, "
                "or like unrelated patterns placed next to each other? If unrelated collage, "
                "return true. Otherwise return false."
            ),
        },
    },
}


# Aliases — some callers use underscores, some use hyphens
_MATERIAL_ALIASES = {
    "landing_hero": "landing-hero",
    "concept_illustration": "concept-illustration",
    "brand_scene": "illustrated-brand-world",
    "campaign_poster": "proof-poster",
    "pattern_system": "site-pattern-tile",
    "system_explainer_illustration": "system-explainer-illustration",
    "editorial_metaphor_illustration": "editorial-metaphor-illustration",
    "illustrated_brand_world": "illustrated-brand-world",
    "proof_poster": "proof-poster",
    "site_pattern_tile": "site-pattern-tile",
    "pattern_board": "pattern-board",
    "brand-scene": "illustrated-brand-world",
    "campaign-poster": "proof-poster",
    "pattern-system": "site-pattern-tile",
}


def _normalize_material(material_type: str | None) -> str:
    if not material_type:
        return ""
    key = str(material_type).strip().lower()
    return _MATERIAL_ALIASES.get(key, key)


def material_rubric_key(material_type: str | None) -> str:
    """Return the rubric key for a material type, or empty if no overlay exists.

    Materials without a registered overlay fall through to universal axes only.
    """
    normalized = _normalize_material(material_type)
    overlay = MATERIAL_OVERLAYS.get(normalized)
    if overlay:
        return str(overlay.get("material_rubric_key") or normalized)
    return ""


def axes_for(material_type: str | None) -> list[dict[str, str]]:
    """Return universal axes plus any material-specific overlay axes.

    Materials without an overlay get only the universal axes.
    """
    normalized = _normalize_material(material_type)
    overlay = MATERIAL_OVERLAYS.get(normalized) or {}
    overlay_axes = list(overlay.get("overlay_axes") or [])
    return list(UNIVERSAL_AXES) + overlay_axes


def disqualifier_for(material_type: str | None) -> dict[str, str] | None:
    """Return the disqualifier rule for this material, or None if no rule."""
    normalized = _normalize_material(material_type)
    overlay = MATERIAL_OVERLAYS.get(normalized) or {}
    return overlay.get("disqualifier")


def to_json_dict(material_type: str | None = None) -> dict[str, Any]:
    """Serialize the registry for bgen show-rubric --format json.

    Without material_type: full registry.
    With material_type: focused view showing universal + overlay + disqualifier for that material.
    """
    if material_type:
        normalized = _normalize_material(material_type)
        return {
            "rubric_version": RUBRIC_VERSION,
            "material_type": normalized,
            "material_rubric_key": material_rubric_key(normalized),
            "universal_axes": list(UNIVERSAL_AXES),
            "overlay_axes": (MATERIAL_OVERLAYS.get(normalized) or {}).get("overlay_axes", []),
            "disqualifier": disqualifier_for(normalized),
        }
    return {
        "rubric_version": RUBRIC_VERSION,
        "universal_axes": list(UNIVERSAL_AXES),
        "materials": {
            key: {
                "material_rubric_key": overlay.get("material_rubric_key"),
                "overlay_axes": list(overlay.get("overlay_axes") or []),
                "disqualifier": overlay.get("disqualifier"),
            }
            for key, overlay in MATERIAL_OVERLAYS.items()
        },
    }


def to_markdown() -> str:
    """Regenerate critic-agent-readable rubric prose from the registry.

    Used by M1 to update .claude/agents/brand-critic.md (and mirrors). The
    output MUST document both the v1 narrative rubric and the v2 structured
    rubric so the critic agent can handle both packet shapes during the
    transition.
    """
    lines: list[str] = []
    lines.append(f"# Scoring rubric (rubric_version: {RUBRIC_VERSION})")
    lines.append("")
    lines.append(
        "This section is regenerated from `brand_gen/scoring/rubric_registry.py`. "
        "Do not edit by hand. Edits go into the Python module; then regenerate."
    )
    lines.append("")
    lines.append("## Packet shape contract")
    lines.append("")
    lines.append(
        "- **If `rubric_version` is present on the critique packet**: use the "
        "structured v2 rubric below. Score every universal axis and every "
        "overlay axis the material declares. Populate `axis_scores` (1–5 "
        "integers) and `axis_rationales` (1–2 sentences each). Check the "
        "material's disqualifier rule if one exists."
    )
    lines.append(
        "- **If `rubric_version` is absent**: use the v1 narrative rubric "
        "(composition / material_truth / brand_coherence / restraint), as in "
        "the prior critic prose. Do not attempt to populate v2 fields."
    )
    lines.append("")
    lines.append("## v2 universal axes (always scored)")
    lines.append("")
    for axis in UNIVERSAL_AXES:
        lines.append(f"### {axis['name']}")
        lines.append(axis["definition"])
        lines.append("")
    lines.append("## v2 material-specific overlays")
    lines.append("")
    lines.append(
        "Overlays ADD axes on top of the universal 5. They do not replace. "
        "The material's overlay also declares a disqualifier: if the "
        "disqualifier triggers, the overall decision is auto-fail regardless "
        "of axis scores."
    )
    lines.append("")
    for material_key, overlay in MATERIAL_OVERLAYS.items():
        lines.append(f"### {material_key}")
        lines.append("")
        lines.append("**Overlay axes:**")
        for axis in overlay.get("overlay_axes", []):
            lines.append(f"- **{axis['name']}** — {axis['definition']}")
        lines.append("")
        dq = overlay.get("disqualifier")
        if dq:
            lines.append(f"**Disqualifier (`{dq['rule_id']}`):**")
            lines.append(dq["description"])
            lines.append("")
    lines.append("## v2 aggregation")
    lines.append("")
    lines.append(
        "Overall score uses min-biased aggregation across all scored axes "
        "(universal + overlay). If any axis is <2, overall <=2. If the "
        "disqualifier triggers, overall = 1 (auto-fail). Surface `approve` "
        "when overall >=3 and no disqualifier triggered."
    )
    lines.append("")
    lines.append("## v1 narrative rubric (for packets without rubric_version)")
    lines.append("")
    lines.append(
        "Axes: `composition`, `material_truth`, `brand_coherence`, `restraint`. "
        "Score each 1–5, compute mean. mean < 3 → ITERATE, mean >= 3 → APPROVED. "
        "No axis definitions enforced here; use the existing critic prose. "
        "This path is only used when `rubric_version` is absent from the packet."
    )
    lines.append("")
    return "\n".join(lines) + "\n"
