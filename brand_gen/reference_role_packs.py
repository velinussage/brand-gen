"""Reference role packs, reference quality, and inspiration selection.

Handles everything related to reference images and their role assignments
during material planning: quality evaluation, role pack resolution from
workspace example captures, inspiration source selection and translation.

Key functions:
    resolve_reference_role_pack      — resolve a role pack from workspace captures
    suggest_reference_role_pack      — suggest candidates (agent picks from these)
    collect_example_capture_lookup   — scan workspace for example captures
    evaluate_reference_quality       — quality-check selected reference images
    select_inspiration_sources       — rank and shortlist inspiration sources
    resolve_explicit_inspiration_selection — resolve agent's explicit picks
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

from .runtime import *

__all__ = [
    # Reference quality
    "source_risk_rank",
    "reference_capture_quality",
    "reference_looks_like_product_proof",
    "plan_implies_motif_reference",
    "evaluate_reference_quality",
    "evaluate_reference_role_assignments",
    "evaluate_policy_setup_risks",
    # Reference translation
    "default_reference_translation",
    "build_selected_role_translation",
    "build_inspiration_translation_summary",
    "merge_source_metadata",
    # Reference role pack resolution
    "collect_example_capture_lookup",
    "resolve_reference_role_pack",
    "suggest_reference_role_pack",
    "build_role_pack_override_from_plan",
    # Inspiration selection
    "select_inspiration_sources",
    "resolve_explicit_inspiration_selection",
    # Shared utilities (public — used across modules)
    "normalize_inspiration_key",
    "stable_mechanic_id",
    # Constants
    "GENERIC_REFERENCE_PATHS",
    "MOTIF_TRIGGER_TERMS",
]


def source_risk_rank(value: str | None) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get((value or "medium").strip().lower(), 1)


def merge_source_metadata(source: dict, registry_lookup: dict[str, dict]) -> dict:
    registry_item = registry_lookup.get(source.get("key") or "", {})
    merged = dict(registry_item)
    merged.update(source or {})
    for key in ("notes", "name", "category", "url"):
        if not merged.get(key):
            merged[key] = registry_item.get(key) or source.get(key) or ""
    for key in ("tags", "role_strengths", "borrow_mechanics", "avoid_literal", "best_for"):
        merged[key] = merged.get(key) or registry_item.get(key) or []
    merged["direct_generation_risk"] = merged.get("direct_generation_risk") or registry_item.get("direct_generation_risk") or "medium"
    merged["translation_only"] = bool(merged.get("translation_only") or registry_item.get("translation_only"))
    return merged


GENERIC_REFERENCE_PATHS = {"", "/", "/work", "/work/", "/cases", "/cases/", "/projects", "/projects/", "/case-studies", "/case-studies/"}
MOTIF_TRIGGER_TERMS = [
    "motif",
    "pattern",
    "background",
    "geometric",
    "brand frame",
    "carrier",
    "band",
    "lattice",
    "route",
    "grid",
    "shape language",
]


def reference_capture_quality(item: dict) -> tuple[str, list[str]]:
    path = str(item.get("path") or "")
    source_key = str(item.get("source_key") or item.get("key") or "").lower()
    notes = str(item.get("notes") or "").lower()
    url = str(item.get("url") or item.get("source_url") or "")
    reasons: list[str] = []
    if source_key.startswith("custom-") or "/product-screens/" in path:
        return "custom-proof", reasons
    parsed_path = urlparse(url).path if url else ""
    normalized_path = parsed_path.rstrip("/") or "/"
    if "homepage" in notes or source_key.endswith("-home") or source_key.endswith("-homepage"):
        reasons.append("reference is captured from a generic homepage")
        return "generic-overview", reasons
    if normalized_path in GENERIC_REFERENCE_PATHS:
        reasons.append(f"reference URL is a generic overview path ({normalized_path})")
        return "generic-overview", reasons
    if any(segment in normalized_path for segment in ["/work/", "/cases/", "/projects/", "/case-studies/"]):
        return "targeted-case-study", reasons
    if "/examples/" in path:
        return "captured-example", reasons
    return "custom", reasons


def plan_implies_motif_reference(material_type: str | None, plan: dict | None = None, raw_prompt: str = "") -> bool:
    material_key = role_pack_material_key(material_type)
    if material_key not in INTERFACE_MATERIAL_KEYS:
        return False
    parts = [raw_prompt]
    if plan:
        parts.extend([
            str(plan.get("system_mechanic") or ""),
            str(plan.get("purpose") or ""),
            str(plan.get("product_truth_expression") or ""),
            " ".join(str(item) for item in (plan.get("push") or [])),
            " ".join(str(item) for item in (plan.get("preserve") or [])),
        ])
    haystack = " ".join(parts).lower()
    return any(term in haystack for term in MOTIF_TRIGGER_TERMS)


def evaluate_reference_quality(material_key: str, selected_roles: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for item in selected_roles or []:
        role = str(item.get("role") or "").strip().lower()
        quality, reasons = reference_capture_quality(item)
        item["reference_quality"] = quality
        item["reference_quality_reasons"] = reasons
        if material_key in INTERFACE_MATERIAL_KEYS and role in {"composition", "application"} and quality == "generic-overview":
            source_name = item.get("source_name") or item.get("source_key") or role
            errors.append(
                f"{role.title()} ref '{source_name}' is a generic homepage/work index capture; use a targeted case-study or product-presentation crop instead."
            )
        elif quality == "generic-overview":
            warnings.append(f"{role.title()} ref '{item.get('source_name') or item.get('source_key')}' is a generic overview capture.")
    return {"errors": errors, "warnings": warnings}


def reference_looks_like_product_proof(item: dict) -> bool:
    quality = str(item.get("reference_quality") or "").strip().lower()
    if quality == "custom-proof":
        return True
    haystack = " ".join(
        str(item.get(key) or "")
        for key in ("path", "source_key", "source_name", "notes", "url", "source_url")
    ).lower()
    proof_terms = [
        "/product-screens/",
        "product-screen",
        "product screen",
        "screenshot",
        "screen",
        "viewport",
        "dashboard",
        "browser",
        "feed",
        "app",
        "ui",
        "workflow",
        "prompt-live",
        "library-live",
        "home-feed",
        "cli",
    ]
    return any(term in haystack for term in proof_terms)


def evaluate_reference_role_assignments(material_key: str, selected_roles: list[dict]) -> dict:
    warnings: list[str] = []
    proof_sensitive_materials = INTERFACE_MATERIAL_KEYS | {"social", "landing_hero"}
    for item in selected_roles or []:
        role = str(item.get("role") or "").strip().lower()
        source_name = item.get("source_name") or item.get("source_key") or role or "reference"
        looks_like_product_proof = reference_looks_like_product_proof(item)
        quality = str(item.get("reference_quality") or "").strip().lower()

        if material_key in proof_sensitive_materials and role in {"composition", "application", "motif"} and looks_like_product_proof:
            warnings.append(
                f"Ref '{source_name}' looks like product proof but is assigned to `{role}`; keep the explicit pick if intentional, "
                "but consider assigning a `product_truth` role so real UI/workflow truth stays authoritative."
            )
        if role == "product_truth" and quality == "generic-overview":
            warnings.append(
                f"Ref '{source_name}' is assigned to `product_truth` but looks like a generic overview capture; "
                "keep the explicit pick if intentional, but verify it carries concrete product truth."
            )
        elif role == "product_truth" and not looks_like_product_proof and material_key in proof_sensitive_materials:
            warnings.append(
                f"Ref '{source_name}' is assigned to `product_truth` but does not look like explicit product proof; "
                "keep the explicit pick if intentional, but verify it carries real UI/workflow truth."
            )
    return {"warnings": dedupe_keep_order(warnings)}


def evaluate_policy_setup_risks(
    material_type: str | None,
    *,
    brand_policy: dict | None = None,
    selected_roles: list[dict] | None = None,
    approved_assets: list[str] | None = None,
    passed_reference_paths: list[str] | None = None,
    raw_prompt: str | None = None,
    has_base_image: bool = False,
    render_backend: str | None = None,
    source_url: str | None = None,
    entity_type: str | None = None,
    selected_surface_strategy: str | None = None,
) -> list[str]:
    material_key = role_pack_material_key(material_type) or str(material_type or "").strip().lower().replace("-", "_")
    selected_roles = [dict(item) for item in (selected_roles or [])]
    selected_role_names = [str(item.get("role") or "").strip() for item in selected_roles if str(item.get("role") or "").strip()]
    brand_policy = brand_policy or MATERIAL_BRAND_POLICIES.get(material_key, {})
    approved_assets = [str(item).strip() for item in (approved_assets or []) if str(item).strip()]
    proof_sensitive_materials = INTERFACE_MATERIAL_KEYS | {"social", "landing_hero"}
    decorative_roles = {"composition", "application", "motif", "motion"}

    has_explicit_product_truth_role = "product_truth" in selected_role_names
    reference_set_has_product_truth_emphasis = any(
        str(item.get("role") or "").strip() == "product_truth" or reference_looks_like_product_proof(item)
        for item in selected_roles
    )
    raw_lower = str(raw_prompt or "").lower()
    render_backend = str(render_backend or "").strip().lower()
    source_url = str(source_url or "").strip()
    entity_type = str(entity_type or "").strip().lower()
    selected_surface_strategy = str(selected_surface_strategy or "").strip().lower()
    structured_governed_html = bool(
        render_backend == "html"
        and source_url
        and entity_type in {"prompt", "skill", "library"}
        and selected_surface_strategy
    )
    screenshot_led_setup = bool(has_base_image) or bool(passed_reference_paths)
    if not screenshot_led_setup:
        screenshot_led_setup = any(reference_looks_like_product_proof(item) for item in selected_roles)
    if not screenshot_led_setup:
        screenshot_led_setup = any(
            term in raw_lower
            for term in (
                "screenshot",
                "proof",
                "crop",
                "viewport",
                "feed",
                "ui",
                "screen",
                "base image",
                "base-image",
            )
        )
    if structured_governed_html and not has_base_image:
        ref_paths = [str(item).lower() for item in (passed_reference_paths or []) if str(item).strip()]
        screenshot_like_ref = any(
            token in path
            for path in ref_paths
            for token in ("screenshot", "screen", "proof", "crop", "viewport")
        )
        if not screenshot_like_ref:
            screenshot_led_setup = False

    risks: list[str] = []
    if material_key in proof_sensitive_materials and not has_explicit_product_truth_role:
        risks.append(
            "Policy/setup risk: proof-sensitive material lacks a selected `product_truth` role; the setup may drift toward decorative framing."
        )
    if brand_policy.get("logo_mode") == "required" and not approved_assets:
        risks.append(
            "Policy/setup risk: material policy requires an approved logo/mark asset, but brand memory has no icon, wordmark, or lockup path."
        )
    if material_key in proof_sensitive_materials and selected_role_names and set(selected_role_names).issubset(decorative_roles):
        risks.append(
            "Policy/setup risk: prompt/reference setup is decorative-only for this proof-sensitive material; selected roles are framing-oriented rather than product-truth-oriented."
        )
    if material_key in proof_sensitive_materials and selected_roles and not reference_set_has_product_truth_emphasis:
        risks.append(
            "Policy/setup risk: reference set lacks clear product-truth emphasis for this proof-sensitive material."
        )
    if passed_reference_paths is not None and brand_policy.get("product_truth_expression") and material_key in proof_sensitive_materials:
        if not passed_reference_paths and not has_base_image:
            risks.append(
                "Policy/setup risk: material policy expects explicit product proof or branded claim, but the current execution setup is not carrying passed product-truth references."
            )
        elif not reference_set_has_product_truth_emphasis:
            risks.append(
                "Policy/setup risk: passed references do not clearly emphasize product truth for this proof-sensitive material."
            )
    if material_key == "announcement_card" and screenshot_led_setup:
        risks.append(
            "Policy/setup risk: announcement-card is headline/illustration-led, but the current setup is screenshot-led proof. Prefer a state-card/social surface, or reduce proof to a tiny deterministic chip instead of a full screenshot."
        )
    return dedupe_keep_order(risks)


def default_reference_translation(role: str, item: dict) -> dict:
    defaults = ROLE_TRANSLATION_DEFAULTS.get(role, {})
    borrow = dedupe_keep_order((item.get("borrow_mechanics") or []) + (defaults.get("borrow") or []))
    avoid = dedupe_keep_order((item.get("avoid_literal") or []) + (defaults.get("avoid") or []))
    risk = (item.get("direct_generation_risk") or "medium").strip().lower()
    translation_only = bool(item.get("translation_only"))
    summary_parts = []
    if borrow:
        summary_parts.append(f"Borrow {', '.join(borrow[:4])}")
    if avoid:
        summary_parts.append(f"do not borrow {', '.join(avoid[:4])}")
    if translation_only:
        summary_parts.append("use only as a translated mechanic reference, not a direct style target")
    elif risk == "high":
        summary_parts.append("treat as a high-risk reference and weaken its influence")
    return {
        "borrow_mechanics": borrow,
        "avoid_literal": avoid,
        "direct_generation_risk": risk,
        "translation_only": translation_only,
        "summary": "; ".join(summary_parts).strip(),
    }


def build_selected_role_translation(item: dict) -> dict:
    translation = default_reference_translation(item.get("role") or "", item)
    return {
        "role": item.get("role") or "",
        "source_key": item.get("source_key") or "",
        "source_name": item.get("source_name") or item.get("source_key") or "",
        **translation,
    }


def build_inspiration_translation_summary(selected_roles: list[dict]) -> dict:
    translations = [build_selected_role_translation(item) for item in selected_roles]
    rule = (
        "Translate inspiration into mechanics only. Borrow hierarchy, system logic, application attitude, or motion pacing from references, "
        "but never borrow another brand's logo, typography, copy, literal symbols, or product structure."
    )
    return {
        "rule": rule,
        "references": translations,
    }


def normalize_inspiration_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def stable_mechanic_id(source_key: str, label: str) -> str:
    digest = hashlib.sha1(f"{source_key}|{label}".encode("utf-8")).hexdigest()[:12]
    return f"mechanic_{digest}"


def select_inspiration_sources(
    source_records: list[dict],
    *,
    selected_roles: list[dict],
    material_type: str | None,
    max_sources: int | None = None,
) -> dict:
    material_key = role_pack_material_key(material_type)
    is_interface = material_key in INTERFACE_MATERIAL_KEYS
    limit = max_sources or (1 if is_interface else 2)
    role_keys = {
        normalize_inspiration_key(item.get("source_key") or item.get("source_name") or "")
        for item in (selected_roles or [])
        if str(item.get("source_key") or item.get("source_name") or "").strip()
    }
    ranked: list[tuple[float, int, dict]] = []
    reasons: list[str] = []
    for idx, item in enumerate(source_records or []):
        source_key = normalize_inspiration_key(item.get("source_key") or item.get("source_name") or "")
        score = 0.0
        if source_key and source_key in role_keys:
            score += 5.0
        path_hint = str(item.get("design_memory_path") or "").lower()
        if is_interface and "saas-product-specialists" in path_hint:
            score += 2.0
        if not is_interface and "premium-branding" in path_hint:
            score += 2.0
        if idx == 0:
            score += 0.25
        ranked.append((score, idx, item))
    picked = [item for _, _, item in sorted(ranked, key=lambda row: (-row[0], row[1]))[:limit]]
    if not picked:
        return {
            "records": [],
            "mode": "none",
            "reason": "No configured inspiration sources were available for this brand.",
        }
    if any(normalize_inspiration_key(item.get("source_key") or item.get("source_name") or "") in role_keys for item in picked):
        reasons.append("matched configured inspiration sources to selected role-pack references")
    if is_interface:
        reasons.append("kept interface inspiration narrow to reduce prompt bloat")
    else:
        reasons.append("used a small branded inspiration subset instead of the full doctrine merge")
    return {
        "records": picked,
        "mode": "advisory_shortlist",
        "reason": "; ".join(reasons),
    }


def resolve_explicit_inspiration_selection(
    source_records: list[dict],
    *,
    picks: list[str] | None = None,
    recommended_records: list[dict] | None = None,
    accept_recommendations: bool = False,
) -> dict:
    source_records = list(source_records or [])
    recommendations = list(recommended_records or [])
    if accept_recommendations:
        return {
            "records": recommendations,
            "mode": "agent_confirmed_recommendations",
            "reason": "Agent explicitly accepted the recommended inspiration shortlist.",
        }
    normalized_lookup: dict[str, dict] = {}
    for item in source_records:
        keys = {
            normalize_inspiration_key(item.get("source_key") or ""),
            normalize_inspiration_key(item.get("source_name") or ""),
        }
        for key in keys:
            if key:
                normalized_lookup[key] = item
    selected: list[dict] = []
    seen: set[str] = set()
    for raw in picks or []:
        normalized = normalize_inspiration_key(raw)
        if not normalized:
            continue
        match = normalized_lookup.get(normalized)
        if not match:
            continue
        source_key = normalize_inspiration_key(match.get("source_key") or match.get("source_name") or "")
        if source_key in seen:
            continue
        seen.add(source_key)
        selected.append(match)
    if selected:
        return {
            "records": selected,
            "mode": "agent_selected",
            "reason": "Agent explicitly selected inspiration sources for this plan.",
        }
    return {
        "records": [],
        "mode": "unselected",
        "reason": "No inspiration shortlist was explicitly confirmed; keep recommendations advisory until the agent chooses.",
    }


def collect_example_capture_lookup(brand_dir: Path) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    examples_root = brand_dir / "examples"
    if not examples_root.exists():
        return lookup
    registry_lookup = load_source_registry_lookup()
    for source_json in examples_root.glob("*/*/source.json"):
        source = merge_source_metadata(load_json_file(source_json), registry_lookup)
        if not source:
            continue
        source_root = source_json.parent
        screenshots_dir = source_root / "screenshots"
        candidates = [
            screenshots_dir / "viewport.png",
            screenshots_dir / "full.png",
            source_root / "viewport.png",
            source_root / "full.png",
        ]
        image_path = next((path for path in candidates if path.exists() and path_media_kind(path) == "image"), None)
        if not image_path:
            continue
        role_assets = find_role_asset_paths(source_root)
        key = source.get("key") or source_json.parent.name
        lookup[key] = {
            "key": key,
            "name": source.get("name") or key,
            "notes": source.get("notes") or "",
            "tags": source.get("tags") or [],
            "role_strengths": source.get("role_strengths") or [],
            "borrow_mechanics": source.get("borrow_mechanics") or [],
            "avoid_literal": source.get("avoid_literal") or [],
            "direct_generation_risk": source.get("direct_generation_risk") or "medium",
            "translation_only": bool(source.get("translation_only")),
            "best_for": source.get("best_for") or [],
            "path": image_path.resolve(),
            "role_assets": {role: str(path) for role, path in role_assets.items()},
            "source_root": str(source_root.resolve()),
        }
    return lookup


def resolve_reference_role_pack(brand_dir: Path, material_type: str | None) -> dict:
    material_key = role_pack_material_key(material_type)
    config = load_reference_role_packs()
    pack = (config.get("packs") or {}).get(material_key) or {}
    if not pack:
        return {
            "material_key": material_key,
            "roles": [],
            "paths": [],
            "motion_paths": [],
            "snippet": "",
            "missing_roles": [],
            "required_roles": [],
            "priority": [],
        }
    role_help = config.get("roles") or {}
    lookup = collect_example_capture_lookup(brand_dir)
    priority = [role for role in (pack.get("priority") or []) if role in ROLE_PACK_TAG_PRIORITY]
    for role in ROLE_PACK_TAG_PRIORITY:
        if role not in priority:
            priority.append(role)
    required_roles = [role for role in (pack.get("required_roles") or []) if role in ROLE_PACK_TAG_PRIORITY]
    selection_note = (pack.get("selection_note") or "").strip()
    prefer_unique_sources = bool(pack.get("prefer_unique_sources", True))
    selected_roles: list[dict] = []
    missing_roles: list[str] = []
    used_sources: set[str] = set()
    for role in priority:
        source_keys = pack.get(role) or []
        picked = None
        fallback = None
        for key in source_keys:
            source = lookup.get(key)
            if not source:
                continue
            role_assets = source.get("role_assets") or {}
            asset_path = Path(role_assets.get(role) or source["path"]).expanduser().resolve()
            candidate = {
                "role": role,
                "role_help": role_help.get(role) or "",
                "source_key": source["key"],
                "source_name": source["name"],
                "notes": source["notes"],
                "path": str(asset_path),
                "asset_kind": path_media_kind(asset_path),
                "role_strengths": source.get("role_strengths") or [],
                "borrow_mechanics": source.get("borrow_mechanics") or [],
                "avoid_literal": source.get("avoid_literal") or [],
                "direct_generation_risk": source.get("direct_generation_risk") or "medium",
                "translation_only": bool(source.get("translation_only")),
                "best_for": source.get("best_for") or [],
                "used_role_asset": role in role_assets,
            }
            if not prefer_unique_sources or source["key"] not in used_sources:
                picked = candidate
                break
            if fallback is None:
                fallback = candidate
        if not picked:
            picked = fallback
        if not picked:
            missing_roles.append(role)
            continue
        selected_roles.append(picked)
        used_sources.add(picked["source_key"])

    paths = [Path(item["path"]) for item in selected_roles if item.get("asset_kind") == "image"]
    motion_paths = [Path(item["path"]) for item in selected_roles if item.get("asset_kind") == "video"]
    snippet_lines = []
    if selected_roles:
        snippet_lines.append("Reference role pack for this material:")
        if priority:
            snippet_lines.append(f"- Primary role order: {', '.join(priority[:3])}")
        if required_roles:
            snippet_lines.append(f"- Required roles: {', '.join(required_roles)}")
        snippet_lines.append(f"- Prefer unique sources: {'yes' if prefer_unique_sources else 'no'}")
        if selection_note:
            snippet_lines.append(f"- Selection note: {selection_note}")
        for item in selected_roles:
            line = f"- {item['role']}: {item['source_name']}"
            if item["notes"]:
                line += f" — {item['notes']}"
            if item.get("used_role_asset"):
                line += " [role-specific asset]"
            if item.get("translation_only"):
                line += " [translation-only]"
            if item.get("role_help"):
                line += f" ({item['role_help']})"
            snippet_lines.append(line)
            translation = default_reference_translation(item["role"], item)
            if translation.get("summary"):
                snippet_lines.append(f"  Translate it as: {translation['summary']}")
        snippet_lines.append("- Treat the first two primary roles as the strongest style inputs; support roles are sanity checks, not equal blends.")
    missing_required = [role for role in required_roles if role not in {item.get('role') for item in selected_roles}]
    return {
        "material_key": material_key,
        "roles": selected_roles,
        "paths": paths,
        "motion_paths": motion_paths,
        "snippet": "\n".join(snippet_lines).strip(),
        "missing_roles": missing_roles,
        "required_roles": required_roles,
        "missing_required_roles": missing_required,
        "priority": priority,
        "prefer_unique_sources": prefer_unique_sources,
    }


def suggest_reference_role_pack(brand_dir: Path, material_type: str | None) -> dict:
    material_key = role_pack_material_key(material_type)
    config = load_reference_role_packs()
    pack = (config.get("packs") or {}).get(material_key) or {}
    role_help = config.get("roles") or {}
    lookup = collect_example_capture_lookup(brand_dir)
    priority = [role for role in (pack.get("priority") or []) if role in ROLE_PACK_TAG_PRIORITY]
    for role in ROLE_PACK_TAG_PRIORITY:
        if role not in priority:
            priority.append(role)
    required_roles = [role for role in (pack.get("required_roles") or []) if role in ROLE_PACK_TAG_PRIORITY]
    candidates_by_role: dict[str, list[dict]] = {}
    for role in priority:
        candidates: list[dict] = []
        for key in pack.get(role) or []:
            source = lookup.get(key)
            if not source:
                continue
            role_assets = source.get("role_assets") or {}
            asset_path = Path(role_assets.get(role) or source["path"]).expanduser().resolve()
            candidates.append(
                {
                    "role": role,
                    "role_help": role_help.get(role) or "",
                    "source_key": source["key"],
                    "source_name": source["name"],
                    "notes": source["notes"],
                    "path": str(asset_path),
                    "asset_kind": path_media_kind(asset_path),
                    "borrow_mechanics": source.get("borrow_mechanics") or [],
                    "avoid_literal": source.get("avoid_literal") or [],
                    "direct_generation_risk": source.get("direct_generation_risk") or "medium",
                    "translation_only": bool(source.get("translation_only")),
                    "best_for": source.get("best_for") or [],
                    "used_role_asset": role in role_assets,
                }
            )
        candidates_by_role[role] = candidates
    return {
        "material_key": material_key,
        "priority": priority,
        "required_roles": required_roles,
        "prefer_unique_sources": bool(pack.get("prefer_unique_sources", True)),
        "selection_note": (pack.get("selection_note") or "").strip(),
        "candidates": candidates_by_role,
    }


def build_role_pack_override_from_plan(plan: dict) -> dict:
    role_pack = plan.get("role_pack") or {}
    selected = role_pack.get("selected_roles") or role_pack.get("roles") or []
    material_key = role_pack.get("material_key") or role_pack_material_key(plan.get("material_type"))
    selected = [dict(item) for item in selected]
    for item in selected:
        if "reference_quality" not in item or "reference_quality_reasons" not in item:
            quality, reasons = reference_capture_quality(item)
            item["reference_quality"] = quality
            item["reference_quality_reasons"] = reasons
    configured_required_roles = role_pack.get("configured_required_roles") or role_pack.get("required_roles") or []
    required_roles = role_pack.get("required_roles") or []
    selected_role_names = [str(item.get("role") or "").strip() for item in selected if str(item.get("role") or "").strip()]
    missing_required_roles = [role for role in required_roles if role not in selected_role_names]
    paths = [Path(item["path"]).expanduser().resolve() for item in selected if path_media_kind(item["path"]) == "image"]
    motion_paths = [Path(item["path"]).expanduser().resolve() for item in selected if path_media_kind(item["path"]) == "video"]
    role_assignment_warnings = dedupe_keep_order(
        list(role_pack.get("role_assignment_warnings") or [])
        + list((evaluate_reference_role_assignments(material_key or "", selected).get("warnings") or []))
    )
    snippet_lines = []
    if selected:
        snippet_lines.append("Planned reference role pack for this run:")
        if role_pack.get("priority"):
            snippet_lines.append(f"- Primary role order: {', '.join(role_pack['priority'])}")
        if configured_required_roles:
            snippet_lines.append(f"- Required roles: {', '.join(configured_required_roles)}")
        if role_pack.get("requirement_mode") == "advisory_inspiration_fallback":
            unavailable = role_pack.get("unavailable_required_roles") or []
            if unavailable:
                snippet_lines.append(
                    f"- Role-pack fallback: no workspace captures were available for {', '.join(unavailable)}; use the selected inspiration shortlist as the fallback guide."
                )
        if role_pack.get("selection_note"):
            snippet_lines.append(f"- Selection note: {role_pack['selection_note']}")
        for warning in role_assignment_warnings:
            snippet_lines.append(f"- Role warning: {warning}")
        for item in selected:
            line = f"- {item['role']}: {item.get('source_name') or item.get('source_key') or 'custom'}"
            if item.get("notes"):
                line += f" — {item['notes']}"
            snippet_lines.append(line)
            translation = item.get("translation") or default_reference_translation(item.get("role") or "", item)
            if translation.get("summary"):
                snippet_lines.append(f"  Translate it as: {translation['summary']}")
    brand_anchor_policy = plan.get("brand_anchor_policy") or {}
    if brand_anchor_policy.get("rule"):
        snippet_lines.append(f"- Brand anchor policy: {brand_anchor_policy['rule']}")
    return {
        "material_key": material_key,
        "roles": selected,
        "paths": paths,
        "motion_paths": motion_paths,
        "snippet": "\n".join(snippet_lines).strip(),
        "missing_roles": [],
        "required_roles": required_roles,
        "configured_required_roles": configured_required_roles,
        "missing_required_roles": missing_required_roles,
        "unavailable_required_roles": role_pack.get("unavailable_required_roles") or [],
        "requirement_mode": role_pack.get("requirement_mode") or "strict",
        "role_assignment_warnings": role_assignment_warnings,
        "priority": role_pack.get("priority") or [],
        "prefer_unique_sources": role_pack.get("prefer_unique_sources", True),
    }
