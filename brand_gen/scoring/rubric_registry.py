"""Rubric registry — source of truth for the v2 scoring rubric.

Inline Python dict. Editable without touching any other file.
`to_markdown()` regenerates the critic agent prose from this registry.
`to_json_dict()` serializes for `bgen show-rubric --format json` and
for any downstream consumer (scorer, eval harness, PR comment bots).

v1 covers 3 materials explicitly: landing-hero, concept-illustration,
brand-scene. Other materials fall through to universal axes only.

To add a material overlay: extend MATERIAL_OVERLAYS with a dict.
To add a universal axis: extend UNIVERSAL_AXES (affects every run — do this
with intent and coordinate with the critic agent prose update).
"""
from __future__ import annotations

from typing import Any


RUBRIC_VERSION = "2026-04-20"


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
    "brand-scene": {
        "material_rubric_key": "brand-scene",
        "overlay_axes": [
            {
                "name": "process_implied",
                "definition": (
                    "Does the environment imply the brand's actual process or work, or "
                    "is it just a tasteful architectural / interior mood piece? Brand "
                    "scenes should feel like the kind of room where the brand's work "
                    "happens — the textures, tools, materials, posture all carry "
                    "evidence of process."
                ),
            },
            {
                "name": "brand_specificity",
                "definition": (
                    "Same definition as concept-illustration. Scenes that feel like "
                    "generic premium interior design score low. Scenes that carry the "
                    "brand's declared material vocabulary (rammed earth, aged stone, "
                    "specific typographic signage, brand palette in the lighting) "
                    "score high."
                ),
            },
        ],
        "disqualifier": {
            "rule_id": "brand-scene-pure-mood-no-process",
            "description": (
                "The scene is pure architectural mood — tasteful interior with no "
                "implied process, activity, tools, or evidence that the brand's "
                "work would happen in this space."
            ),
            "detection_prompt": (
                "Examine the scene. Can you point to specific visual evidence that "
                "the brand's work happens in this space? Examples of sufficient "
                "evidence: tools arrayed on a surface, documents mid-review, a "
                "typographic signage that matches brand voice, materials in "
                "progress, a figure in working posture. If the scene is purely "
                "decorative architecture / interior mood with no process evidence, "
                "return true. Otherwise return false."
            ),
        },
    },
}


# Aliases — some callers use underscores, some use hyphens
_MATERIAL_ALIASES = {
    "landing_hero": "landing-hero",
    "concept_illustration": "concept-illustration",
    "brand_scene": "brand-scene",
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
