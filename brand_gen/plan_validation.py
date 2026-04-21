"""Material plan, set manifest, and identity validation.

Pure validation functions — they check data and return structured reports
with errors, warnings, and scores.  No plan creation or identity analysis
lives here (those are in ``plan_builder``).

Key functions:
    validate_material_plan_dict  — validate a single material plan dict
    validate_set_manifest_dict   — validate a multi-material set manifest
    validate_identity_summary    — validate brand identity completeness
"""
from __future__ import annotations

import re
from pathlib import Path

from .brand_policy import normalize_material_brand_policy, summarize_identity
from .request_intent import requires_standalone_illustration_material
from .runtime import *

__all__ = [
    "validate_material_plan_dict",
    "validate_set_manifest_dict",
    "validate_identity_summary",
    "detect_enumerated_categories",
    "plan_has_text_ban",
    "normalize_complexity_tier",
    "complexity_tier_enumeration_min_items",
]

# Complexity tier controls how many named elements the brief may carry.
# Simple: ≤2 named elements — one clear system mechanic only. This is the
#   default for concept-illustration and brand-scene based on the user
#   feedback around v180/v181 ("Wants a simpler Sage illus").
# Moderate: ≤4 named elements — balanced scope for most editorial work.
# Dense: unlimited — opt-in for storyboards and multi-scene films where
#   enumerating capability flows is the point.
_COMPLEXITY_TIERS = ("simple", "moderate", "dense")
_COMPLEXITY_TIER_THRESHOLDS = {
    "simple": 2,
    "moderate": 4,
    "dense": 99,  # effectively disabled
}
_DEFAULT_TIER_BY_MATERIAL = {
    "concept-illustration": "simple",
    "concept_illustration": "simple",
    "brand-scene": "simple",
    "brand_scene": "simple",
}


def normalize_complexity_tier(
    requested: str | None,
    *,
    material_type: str | None = None,
) -> str:
    """Resolve a valid complexity tier string.

    Precedence: explicit caller argument > per-material default > "moderate".
    Invalid values fall back to the per-material default.
    """
    if requested and str(requested).lower().strip() in _COMPLEXITY_TIERS:
        return str(requested).lower().strip()
    if material_type:
        default = _DEFAULT_TIER_BY_MATERIAL.get(str(material_type).lower().strip())
        if default:
            return default
    return "moderate"


def complexity_tier_enumeration_min_items(tier: str) -> int:
    """Return the named-category threshold that triggers the enumerated-
    categories warning for the given tier. A higher number means the
    detector tolerates longer lists.
    """
    return _COMPLEXITY_TIER_THRESHOLDS.get(tier, _COMPLEXITY_TIER_THRESHOLDS["moderate"])


# Phrases that signal a "no text", "no labels", "no headlines" constraint.
# When one of these is present AND the prompt seed enumerates ≥4 named
# categories, the plan is in the v062 / v163-168 / v176-178 failure zone:
# the brief invites labels while the ban forbids them, and the image
# model renders the labels anyway.
_TEXT_BAN_PHRASES = (
    "textless",
    "no text",
    "no invented text",
    "no headline",
    "no headlines",
    "no labels",
    "no label",
    "no copy",
    "no invented copy",
    "no typographic overlays",
    "no typography",
    "no rendered text",
    "no visible text",
    "do not render text",
    "avoid text",
    "hard no-text",
    "text-free",
)

# Matches parenthetical enumerations like "(A, B, C, D)" or "(A / B / C / D)".
_PAREN_ENUM_RE = re.compile(r"\(([^()]{3,400})\)")

# Breaks a parenthetical body into candidate items — commas, semicolons,
# slashes, and the word "and".
_ITEM_SPLIT_RE = re.compile(r"[;,]|\band\b|/", flags=re.IGNORECASE)


def detect_enumerated_categories(
    text: str,
    *,
    min_items: int = 4,
) -> list[list[str]]:
    """Return parenthetical enumerations with `min_items` or more items.

    Each return element is the list of items parsed from a single
    parenthetical group. The shape lets callers surface the offending
    phrase in a warning.

    Matches patterns like:
      "six differentiated habitats (skills forge, prompt curation atelier,
       library discovery stacks, provenance/review checkpoints, CLI/MCP
       runtime relay, agent orchestration commons)"
      → returns [["skills forge", "prompt curation atelier", ...]]

    Skips enumerations that are mostly palette tokens or color names
    (those are legitimate style direction, not category labels the
    image model should render).
    """
    if not text or not isinstance(text, str):
        return []
    hits: list[list[str]] = []
    _COLOR_TOKENS = {
        "cream", "terracotta", "sage", "charcoal", "amber", "parchment",
        "ember", "rust", "ivory", "bone", "oak", "stone", "ochre",
        "olive", "moss", "brass", "copper", "walnut", "porcelain",
    }
    for match in _PAREN_ENUM_RE.finditer(text):
        body = match.group(1).strip()
        items = [i.strip(" .'\"") for i in _ITEM_SPLIT_RE.split(body) if i.strip()]
        items = [i for i in items if len(i) > 1 and not i.isdigit()]
        if len(items) < min_items:
            continue
        # Skip color-palette lists so "warm terracotta / sage / amber / parchment"
        # doesn't falsely fire as a named-category enumeration.
        word_tokens = [w.lower() for i in items for w in i.split()]
        if word_tokens and sum(1 for w in word_tokens if w in _COLOR_TOKENS) / len(word_tokens) >= 0.5:
            continue
        hits.append(items)
    return hits


def plan_has_text_ban(plan: dict) -> bool:
    """Return True when the plan's ban list, preserve list, or prompt_seed
    carries a text/labels/headlines prohibition.
    """
    haystack_parts: list[str] = []
    for field in ("prompt_seed", "system_mechanic", "purpose"):
        v = plan.get(field)
        if v:
            haystack_parts.append(str(v))
    for field in ("ban", "preserve", "push"):
        v = plan.get(field) or []
        if isinstance(v, list):
            haystack_parts.extend(str(item) for item in v)
        elif isinstance(v, str):
            haystack_parts.append(v)
    haystack = " ".join(haystack_parts).lower()
    return any(phrase in haystack for phrase in _TEXT_BAN_PHRASES)


def validate_material_plan_dict(plan: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    brand_anchor_policy = plan.get("brand_anchor_policy") or {}
    role_pack = plan.get("role_pack") or {}
    translations = ((plan.get("inspiration_translation") or {}).get("references") or [])
    material_type = plan.get("material_type") or ""
    material_key = role_pack_material_key(material_type)
    role_pack_config = ((load_reference_role_packs().get("packs") or {}).get(material_key) or {})
    configured_required_roles = (
        role_pack.get("configured_required_roles")
        if "configured_required_roles" in role_pack
        else role_pack.get("required_roles") or role_pack_config.get("required_roles") or []
    )
    required_roles = role_pack.get("required_roles") if "required_roles" in role_pack else role_pack_config.get("required_roles") or []
    requirement_mode = str(role_pack.get("requirement_mode") or "strict")
    selected_role_names = [str(item.get("role") or "").strip() for item in (role_pack.get("selected_roles") or []) if str(item.get("role") or "").strip()]
    derived_missing_required = [role for role in required_roles if role not in selected_role_names]

    checks["material_type"] = bool(material_type)
    checks["purpose"] = bool(plan.get("purpose"))
    checks["target_surface"] = bool(plan.get("target_surface"))
    checks["product_truth_expression"] = bool(plan.get("product_truth_expression"))
    checks["abstraction_level"] = bool(plan.get("abstraction_level"))
    checks["brand_anchor_policy"] = bool(brand_anchor_policy.get("rule"))
    checks["system_mechanic"] = bool((plan.get("system_mechanic") or "").strip())
    checks["preserve"] = bool(plan.get("preserve"))
    checks["push"] = bool(plan.get("push"))
    checks["ban"] = bool(plan.get("ban"))
    checks["role_pack_selected_roles"] = bool(role_pack.get("selected_roles")) or not required_roles
    checks["inspiration_translation"] = bool(translations) or not required_roles
    checks["prompt_seed"] = bool(plan.get("prompt_seed"))

    artifact_scope = str(plan.get("artifact_scope") or "").strip().lower()
    selected_inspiration_sources = list(plan.get("selected_inspiration_sources") or [])
    selected_inspiration_keys = [
        str(item.get("source_key") or item.get("source_name") or "").strip()
        for item in selected_inspiration_sources
        if str(item.get("source_key") or item.get("source_name") or "").strip()
    ]
    inspiration_requirements = plan.get("inspiration_requirements") or {}

    # Map plan field names to their CLI flag equivalents
    _FIELD_TO_FLAG: dict[str, str] = {
        "purpose": "--purpose",
        "target_surface": "--target-surface",
        "product_truth_expression": "--product-truth-expression",
        "abstraction_level": "--abstraction-level",
    }

    for key in ("material_type", "purpose", "target_surface", "brand_anchor_policy", "prompt_seed", "system_mechanic", "preserve", "push", "ban"):
        if not checks[key]:
            label = key.replace('_', ' ')
            flag_hint = _FIELD_TO_FLAG.get(key)
            if flag_hint:
                errors.append(f"Missing {label} (add {flag_hint} to the pipeline command).")
            else:
                errors.append(f"Missing {label}.")

    for key in ("product_truth_expression", "abstraction_level", "role_pack_selected_roles", "inspiration_translation"):
        if not checks[key]:
            label = key.replace('_', ' ')
            flag_hint = _FIELD_TO_FLAG.get(key)
            if flag_hint:
                warnings.append(f"Missing {label} (add {flag_hint} to the pipeline command).")
            else:
                warnings.append(f"Missing {label}.")

    if brand_anchor_policy.get("logo_mode") == "required" and not brand_anchor_policy.get("rule"):
        errors.append("Logo-required material is missing a branding rule.")
    if material_key in {"landing_hero", "browser_illustration", "product_banner", "feature_illustration", "social", "feature_animation"} and not plan.get("product_truth_expression"):
        errors.append("Product-led material is missing product truth expression.")

    if requires_standalone_illustration_material(material_key, illustration_only=artifact_scope == "illustration_only"):
        errors.append(
            f"Illustration-only request is using interface material '{material_type}', which tends to produce full-page or page-adjacent chrome. Use a standalone illustration material instead."
        )
    elif artifact_scope == "illustration_only" and material_key == "feature_illustration":
        warnings.append(
            "Illustration-only request is using feature-illustration. This is allowed, but the plan must treat it as standalone artwork rather than a full landing page, hero comp, or browser-framed UI surface."
        )

    # Interface materials MUST have a base_image or source screenshot
    INTERFACE_MATERIAL_TYPES = {"browser_illustration", "landing_hero", "product_banner", "feature_illustration"}
    if material_key in INTERFACE_MATERIAL_TYPES and not plan.get("base_image"):
        errors.append(
            "Interface material is missing base_image (real product screenshot). "
            "Run: bgen capture-product --url <app-url> --out-dir brands/<brand>/product-shots, "
            "then pass --base-image <path> to the pipeline command."
        )

    required_inspiration = bool(inspiration_requirements.get("required"))
    min_selected_sources = int(inspiration_requirements.get("min_selected_sources") or 0)
    if required_inspiration and len(selected_inspiration_keys) < max(1, min_selected_sources):
        errors.append(
            f"Material plan requires an explicit inspiration set ({max(1, min_selected_sources)} selected source{'s' if max(1, min_selected_sources) != 1 else ''} minimum), but only {len(selected_inspiration_keys)} selected inspiration source(s) are attached."
        )
    elif not selected_inspiration_keys and material_key in {"concept_illustration", "brand_scene"}:
        warnings.append("Non-interface illustration plan has no selected inspiration sources; the pipeline may drift into posters, diagrams, or generic abstract brand art.")

    if artifact_scope == "illustration_only" and plan.get("base_image") and material_key not in INTERFACE_MATERIAL_TYPES:
        warnings.append(
            "Standalone illustration plan carries a base_image even though the material is non-interface; direct screenshot scaffolding can drag page text and box geometry into the illustration."
        )

    if required_roles and not role_pack.get("selected_roles"):
        warnings.append("Material plan needs translated role-pack refs.")
    if required_roles and derived_missing_required:
        warnings.append("Material plan is missing required role refs: " + ", ".join(derived_missing_required))
    if requirement_mode == "advisory_inspiration_fallback" and configured_required_roles:
        warnings.append("Required role-pack captures are unavailable in the current workspace; using the selected inspiration shortlist as the fallback guide.")
        unavailable_required_roles = [str(role).strip() for role in (role_pack.get("unavailable_required_roles") or []) if str(role).strip()]
        if unavailable_required_roles:
            warnings.append("Unavailable required role-pack refs: " + ", ".join(unavailable_required_roles))
    if any((item.get("direct_generation_risk") or "").lower() == "high" for item in translations):
        warnings.append("One or more selected references have high direct-generation risk; keep them translated rather than literal.")
    warnings.extend(str(item) for item in (role_pack.get("role_assignment_warnings") or []) if str(item).strip())

    # Enumerated-categories detector: catches the v062 / v163-168 / v176-178
    # failure pattern where the brief lists N named categories in parens and
    # the image model renders them as text labels. When the plan also
    # carries a text ban, promote to an error so generation is blocked.
    # The threshold is tier-aware: simple=2, moderate=4, dense=99 (off).
    tier = normalize_complexity_tier(plan.get("complexity_tier"), material_type=material_type)
    min_items = complexity_tier_enumeration_min_items(tier)
    enum_hits = detect_enumerated_categories(
        str(plan.get("prompt_seed") or ""),
        min_items=min_items,
    )
    if enum_hits:
        preview_items = ", ".join(enum_hits[0][:6])
        if plan_has_text_ban(plan):
            errors.append(
                "Prompt seed enumerates "
                f"{len(enum_hits[0])} named categories ({preview_items}...) "
                "while the plan carries a text ban. Image models reliably "
                "render the enumerated names as labels despite the ban — "
                "this is the v062/v163-168/v176-178 failure pattern. "
                "Collapse the enumeration to a single compositional cue, "
                "or drop the text ban, before generation."
            )
        else:
            warnings.append(
                f"Prompt seed enumerates {len(enum_hits[0])} named categories "
                f"({preview_items}...) — exceeds the '{tier}' complexity tier "
                f"cap ({min_items}). Enumerations tend to encourage the image "
                "model to render the names as labels; consider collapsing to a "
                f"single compositional cue or raising --complexity-tier."
            )

    warnings = dedupe_keep_order(warnings)

    score = sum(1 for passed in checks.values() if passed)
    return {"ok": not errors, "score": score, "max_score": len(checks), "checks": checks, "errors": errors, "warnings": warnings}


def validate_set_manifest_dict(payload: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    materials = payload.get("materials") or []
    template = payload.get("template") or ""
    checks["set_name"] = bool(payload.get("set_name"))
    checks["goal"] = bool(payload.get("goal"))
    checks["template"] = bool(template)
    checks["materials"] = bool(materials)
    checks["brand_anchor_rule"] = bool(payload.get("set_brand_rule"))
    checks["translation_rule"] = bool((payload.get("inspiration_translation") or {}).get("rule"))
    if not checks["set_name"]:
        errors.append("Missing set_name.")
    if not checks["goal"]:
        errors.append("Missing goal.")
    if not checks["materials"]:
        errors.append("Set has no materials.")
    if not checks["brand_anchor_rule"]:
        warnings.append("Set is missing the overall brand-anchor rule.")
    if not checks["translation_rule"]:
        warnings.append("Set is missing the inspiration translation rule.")
    product_led = 0
    abstractish = 0
    for item in materials:
        plan_path = Path(item.get("plan_path") or "").expanduser()
        if not plan_path.exists():
            errors.append(f"Missing plan file: {plan_path}")
            continue
        report = validate_material_plan_dict(load_json_file(plan_path))
        if not report["ok"]:
            errors.append(f"{item.get('material_type') or plan_path.name}: " + "; ".join(report["errors"]))
        if report["warnings"]:
            warnings.append(f"{item.get('material_type') or plan_path.name}: " + "; ".join(report["warnings"]))
        policy = normalize_material_brand_policy(item.get("material_type"))
        if policy.get("abstraction_level") == "low":
            product_led += 1
        else:
            abstractish += 1
    if product_led == 0:
        errors.append("Set needs at least one low-abstraction product-led material.")
    if abstractish > product_led:
        warnings.append("Set contains more abstract/system materials than product-led materials; brand may drift away from the product.")
    score = sum(1 for passed in checks.values() if passed)
    return {"ok": not errors, "score": score, "max_score": len(checks), "checks": checks, "errors": errors, "warnings": warnings}


def validate_identity_summary(profile_path: Path, identity_path: Path, profile: dict, identity: dict) -> dict:
    summary = summarize_identity(profile, identity)
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    checks["profile_exists"] = profile_path.exists()
    checks["identity_exists"] = identity_path.exists()
    checks["brand_name"] = bool(summary["brand_name"])
    checks["summary"] = bool(summary["summary"])
    checks["tone_words"] = bool(summary["tone_words"])
    checks["palette_direction"] = bool(summary["palette_direction"])
    checks["typography_cues"] = bool(summary["typography_cues"])
    checks["typography_roles"] = bool(summary.get("typography_roles"))
    checks["shape_language"] = bool(summary["shape_language"])
    checks["brand_anchors"] = bool(summary["brand_anchors"])
    checks["approved_graphic_devices"] = bool(summary["approved_graphic_devices"])
    checks["component_cues"] = bool(summary["component_cues"])
    checks["prompt_prelude"] = bool(summary["prompt_prelude"])

    design_language = profile.get("design_language") or identity.get("design_language") or {}
    checks["spacing_scale"] = bool(design_language.get("spacing_scale"))
    checks["semantic_palette_roles"] = bool(design_language.get("semantic_palette_roles"))
    checks["design_tokens"] = bool((identity.get("design_tokens") or profile.get("design_tokens") or {}))

    if not checks["profile_exists"]:
        errors.append(f"Missing brand profile: {profile_path}")
    if not checks["identity_exists"]:
        errors.append(f"Missing brand identity: {identity_path}")
    if not checks["brand_name"]:
        errors.append("Missing brand name.")
    if not checks["prompt_prelude"]:
        errors.append("Missing global brand guardrail prompt prelude.")

    for field, label in [
        ("summary", "brand summary"),
        ("tone_words", "tone words"),
        ("palette_direction", "palette direction"),
        ("typography_cues", "typography cues"),
        ("shape_language", "shape/radius cues"),
    ]:
        if not checks[field]:
            warnings.append(f"Missing {label}.")

    if not checks["typography_roles"]:
        warnings.append("No semantic font roles (body/heading/display/mono) stored; typography prompts will be generic.")
    if not checks["brand_anchors"]:
        warnings.append("No brand anchors / logo candidates stored.")
    if not checks["approved_graphic_devices"]:
        warnings.append("No approved non-interface graphic devices stored.")
    if not checks["component_cues"]:
        warnings.append("No component cues stored; outputs may feel generic.")
    if not checks["spacing_scale"]:
        warnings.append("No spacing scale stored; deterministic composition will use generic spacing defaults.")
    if not checks["semantic_palette_roles"]:
        warnings.append("No semantic palette roles stored.")
    if not checks["design_tokens"]:
        warnings.append("No imported design tokens stored.")

    score = sum(1 for passed in checks.values() if passed)
    return {
        "ok": not errors,
        "score": score,
        "max_score": len(checks),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "summary": summary,
        "files": {
            "profile": str(profile_path),
            "identity": str(identity_path),
        },
    }
