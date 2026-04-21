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

from pathlib import Path

from .brand_policy import normalize_material_brand_policy, summarize_identity
from .request_intent import requires_standalone_illustration_material
from .runtime import *

__all__ = [
    "validate_material_plan_dict",
    "validate_set_manifest_dict",
    "validate_identity_summary",
]


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
