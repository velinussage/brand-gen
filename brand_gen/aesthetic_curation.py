"""Aesthetic curation layer for brand-gen.

This module sits above the older per-material aesthetic archetype library.
Archetypes describe *composition paradigms* for a material; capsules describe a
reusable *art-direction / moodboard* that can be selected, learned, and compiled
into prompt language.

The goal is to give image models the same compressed handles humans use
("pastoral storybook animation warmth", "screenprinted proof poster") while
also rendering concrete, production-safe descriptors (medium, palette, line,
lighting, density, negatives) so the prompt does not depend on copying a named
studio or artist.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .runtime_paths import SCRIPT_DIR

_CAPSULES_PATH = SCRIPT_DIR.parent / "data" / "aesthetic_capsules.json"
_PREFS_FILENAME = "aesthetic-preferences.json"
_GENERIC_STYLE_MATCH_TOKENS = {
    "poster",
    "design",
    "brand",
    "system",
    "product",
    "interface",
    "motion",
    "image",
    "visual",
    "graphic",
    "campaign",
}

_MATERIAL_ALIASES = {
    "system_explainer_illustration": "system-explainer-illustration",
    "concept_illustration": "concept-illustration",
    "editorial_metaphor_illustration": "editorial-metaphor-illustration",
    "illustrated_brand_world": "brand-scene",
    "brand_scene": "brand-scene",
    "proof_poster": "proof-poster",
    "campaign_poster": "campaign-poster",
    "x_feed": "x-feed",
    "browser_illustration": "browser-illustration",
    "feature_illustration": "feature-illustration",
    "landing_hero": "landing-hero",
    "product_banner": "product-banner",
    "pattern_system": "pattern-system",
}


def normalize_material_key(material_type: str | None) -> str:
    key = str(material_type or "").strip().lower().replace("_", "-")
    return _MATERIAL_ALIASES.get(key.replace("-", "_"), key)


def _load_data() -> dict[str, Any]:
    if not _CAPSULES_PATH.exists():
        return {"schema_version": 1, "capsules": []}
    return json.loads(_CAPSULES_PATH.read_text())


def load_aesthetic_capsules() -> list[dict[str, Any]]:
    return [dict(item) for item in (_load_data().get("capsules") or []) if isinstance(item, dict)]


def get_aesthetic_capsule(capsule_id: str | None) -> dict[str, Any] | None:
    target = str(capsule_id or "").strip().lower()
    if not target:
        return None
    for capsule in load_aesthetic_capsules():
        ids = [capsule.get("id"), capsule.get("label"), capsule.get("safe_handle")]
        ids.extend(capsule.get("internal_handles") or [])
        if any(str(item or "").strip().lower() == target for item in ids):
            return capsule
    return None


def list_aesthetic_capsules(material_type: str | None = None) -> list[dict[str, Any]]:
    material_key = normalize_material_key(material_type)
    capsules = load_aesthetic_capsules()
    if not material_key:
        return capsules
    return [c for c in capsules if material_key in {normalize_material_key(m) for m in (c.get("material_types") or [])}]


def aesthetic_preferences_path(brand_dir: Path) -> Path:
    return Path(brand_dir).expanduser().resolve() / _PREFS_FILENAME


def normalize_aesthetic_preferences(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = dict(data or {})
    return {
        "schema_version": int(data.get("schema_version") or 1),
        "selected_by_material": dict(data.get("selected_by_material") or {}),
        "preferred_capsules": list(data.get("preferred_capsules") or []),
        "negative_capsules": list(data.get("negative_capsules") or []),
        "style_dislikes": list(data.get("style_dislikes") or []),
        "style_likes": list(data.get("style_likes") or []),
        "updated_at": str(data.get("updated_at") or ""),
    }


def load_aesthetic_preferences(brand_dir: Path | None) -> dict[str, Any]:
    if not brand_dir:
        return normalize_aesthetic_preferences()
    path = aesthetic_preferences_path(brand_dir)
    if not path.exists():
        return normalize_aesthetic_preferences()
    try:
        return normalize_aesthetic_preferences(json.loads(path.read_text()))
    except (json.JSONDecodeError, OSError):
        return normalize_aesthetic_preferences()


def save_aesthetic_preferences(brand_dir: Path, prefs: dict[str, Any]) -> Path:
    path = aesthetic_preferences_path(brand_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefs = normalize_aesthetic_preferences(prefs)
    prefs["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(prefs, indent=2) + "\n")
    return path


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(text or "").lower()) if len(t) >= 3}


def _matches_handle(capsule: dict[str, Any], text: str) -> bool:
    haystack = str(text or "").strip().lower()
    if not haystack:
        return False
    handles = [capsule.get("id"), capsule.get("label"), capsule.get("safe_handle")]
    handles.extend(capsule.get("internal_handles") or [])
    for handle in handles:
        h = str(handle or "").strip().lower()
        if h and h in haystack:
            return True
    hay_tokens = _tokens(haystack)
    for handle in handles:
        handle_tokens = _tokens(str(handle or ""))
        overlap = hay_tokens & handle_tokens
        if handle_tokens and len(overlap) >= min(2, len(handle_tokens)):
            return True
        # Allow a single rare style shorthand token (e.g. "ghibli") to match
        # an internal handle while still rendering only the safe_handle.
        if any(len(token) >= 6 and token not in _GENERIC_STYLE_MATCH_TOKENS and token in overlap for token in handle_tokens):
            return True
    return False


def _capsule_score(capsule: dict[str, Any], *, material_type: str | None, prefs: dict[str, Any], style_text: str) -> tuple[float, list[str]]:
    reasons: list[str] = []
    material_key = normalize_material_key(material_type)
    score = 0.0
    materials = {normalize_material_key(m) for m in capsule.get("material_types") or []}
    if material_key and material_key in materials:
        score += 4.0
        reasons.append("material_match")
    selected = (prefs.get("selected_by_material") or {}).get(material_key)
    if selected and selected == capsule.get("id"):
        score += 5.0
        reasons.append("brand_selected_for_material")
    try:
        from .material_prompt_profiles import get_material_prompt_profile

        profile = get_material_prompt_profile(material_key)
    except Exception:
        profile = None
    recommended_capsules = list((profile or {}).get("best_aesthetic_capsules") or [])
    if capsule.get("id") in recommended_capsules:
        # Earlier profile entries are stronger defaults.
        rank = recommended_capsules.index(capsule.get("id"))
        score += max(1.0, 3.0 - rank * 0.75)
        reasons.append("material_profile_recommended")
    if capsule.get("id") in (prefs.get("preferred_capsules") or []):
        score += 2.5
        reasons.append("brand_preferred")
    if capsule.get("id") in (prefs.get("negative_capsules") or []):
        score -= 8.0
        reasons.append("brand_negative")
    if _matches_handle(capsule, style_text):
        score += 7.0
        reasons.append("style_handle_match")
    # If recent dislikes mention a capsule handle, deprioritize it. If they
    # mention a negative term carried by this capsule, also deprioritize.
    dislikes = " ".join(str(x) for x in prefs.get("style_dislikes") or []).lower()
    if dislikes:
        if _matches_handle(capsule, dislikes):
            score -= 5.0
            reasons.append("recent_style_dislike")
        for term in capsule.get("negative_prompt_terms") or []:
            if str(term or "").lower() in dislikes:
                score -= 1.0
                reasons.append("negative_term_in_dislikes")
                break
    return score, reasons


def _capsule_variant_summary(capsule: dict[str, Any], *, index: int) -> dict[str, Any]:
    desc = capsule.get("style_description") or {}
    axes = [str(item).strip() for item in (capsule.get("style_axes") or []) if str(item).strip()]
    roles = capsule.get("reference_roles") if isinstance(capsule.get("reference_roles"), dict) else {}
    policy = capsule.get("iteration_policy") if isinstance(capsule.get("iteration_policy"), dict) else {}
    thesis_bits = [
        str(capsule.get("safe_handle") or capsule.get("label") or capsule.get("id") or "").strip(),
        str(desc.get("composition") or "").strip(),
    ]
    visual_thesis = " — ".join(item for item in thesis_bits if item)
    return {
        "rank": index,
        "capsule_id": capsule.get("id") or "",
        "label": capsule.get("label") or capsule.get("id") or "",
        "visual_thesis": visual_thesis,
        "difference_axes": axes[:2],
        "style_strength": capsule.get("style_strength_default"),
        "reference_roles": dict(roles or {}),
        "exploration_role": policy.get("exploration_role") or "",
        "when_to_use": list(capsule.get("use_when") or [])[:3],
        "when_to_avoid": list(capsule.get("avoid_when") or [])[:3],
        "negative_prompt_terms": list(capsule.get("negative_prompt_terms") or [])[:7],
        "prompt_preview": render_capsule_prompt(capsule),
    }


def build_aesthetic_direction_brief(
    *,
    brand_dir: Path | None = None,
    material_type: str | None = None,
    style_text: str | None = None,
    count: int = 3,
) -> dict[str, Any]:
    """Return a small moodboard-style branch set for planning.

    This mirrors how visual-reference agents work: explore 2-3 directions at
    the moodboard layer, make the contrast axes explicit, then let the user or
    critic pick one before spending generation tokens.
    """
    prefs = load_aesthetic_preferences(brand_dir) if brand_dir else normalize_aesthetic_preferences()
    candidates = list_aesthetic_capsules(material_type) or load_aesthetic_capsules()
    scored = []
    for capsule in candidates:
        score, reasons = _capsule_score(capsule, material_type=material_type, prefs=prefs, style_text=str(style_text or ""))
        scored.append((score, reasons, capsule))
    scored.sort(key=lambda item: (-item[0], str(item[2].get("id") or "")))
    limit = max(1, min(int(count or 3), 5))
    variants = []
    for idx, (score, reasons, capsule) in enumerate(scored[:limit], start=1):
        item = _capsule_variant_summary(capsule, index=idx)
        item["selection_score"] = score
        item["selection_reasons"] = reasons
        variants.append(item)
    return {
        "schema_type": "aesthetic_direction_brief",
        "schema_version": 1,
        "material_type": normalize_material_key(material_type),
        "style_text": str(style_text or "").strip(),
        "selection_rule": "Explore 2-3 visibly different moodboard branches; choose one before generation. Do not merge all branches unless explicitly asked.",
        "variants": variants,
    }


def select_aesthetic_capsule(
    *,
    brand_dir: Path | None = None,
    material_type: str | None = None,
    requested_capsule: str | None = None,
    style_text: str | None = None,
) -> dict[str, Any]:
    """Select a capsule and return selection metadata.

    `requested_capsule` is authoritative when valid. Otherwise the selector
    scores material compatibility, brand preferences, and any freeform style
    handle/descriptors (e.g. "ghibli aesthetic").
    """
    prefs = load_aesthetic_preferences(brand_dir) if brand_dir else normalize_aesthetic_preferences()
    style_text = str(style_text or "").strip()
    warnings: list[str] = []
    if requested_capsule:
        capsule = get_aesthetic_capsule(requested_capsule)
        if capsule:
            return {
                "capsule": capsule,
                "capsule_id": capsule.get("id") or "",
                "source": "explicit",
                "score": 999.0,
                "reasons": ["explicit"],
                "warnings": [],
                "preferences": prefs,
            }
        warnings.append(f"requested aesthetic capsule not found: {requested_capsule}")

    candidates = list_aesthetic_capsules(material_type) or load_aesthetic_capsules()
    if not candidates:
        return {"capsule": None, "capsule_id": "", "source": "none", "score": 0.0, "reasons": [], "warnings": warnings, "preferences": prefs}
    scored = []
    for capsule in candidates:
        score, reasons = _capsule_score(capsule, material_type=material_type, prefs=prefs, style_text=style_text)
        scored.append((score, reasons, capsule))
    scored.sort(key=lambda item: (-item[0], str(item[2].get("id") or "")))
    score, reasons, capsule = scored[0]
    source = "style_handle" if "style_handle_match" in reasons else ("brand_preference" if any(r.startswith("brand_") for r in reasons) else "material_default")
    return {
        "capsule": capsule,
        "capsule_id": capsule.get("id") or "",
        "source": source,
        "score": score,
        "reasons": reasons,
        "warnings": warnings,
        "preferences": prefs,
    }


def render_capsule_prompt(capsule: dict[str, Any] | None) -> str:
    if not isinstance(capsule, dict) or not capsule:
        return ""
    label = str(capsule.get("label") or capsule.get("id") or "").strip()
    handle = str(capsule.get("safe_handle") or label).strip()
    desc = capsule.get("style_description") or {}
    positive = [str(x).strip() for x in (capsule.get("positive_prompt_terms") or []) if str(x).strip()]
    negative = [str(x).strip() for x in (capsule.get("negative_prompt_terms") or []) if str(x).strip()]
    parts: list[str] = []
    parts.append(f"Aesthetic direction: {label} — use this as a moodboard/style-reference handle, not a literal copy target.")
    if handle:
        parts.append(f"Compressed style handle: {handle}.")
    ordered = ["medium", "palette", "line", "lighting", "composition", "density", "texture"]
    style_bits = [f"{key}: {desc.get(key)}" for key in ordered if str(desc.get(key) or "").strip()]
    motifs = desc.get("motifs") or []
    if motifs:
        style_bits.append("motifs: " + ", ".join(str(x) for x in motifs[:5]))
    if style_bits:
        parts.append("Style translation: " + "; ".join(style_bits) + ".")
    strength = capsule.get("style_strength_default")
    if strength not in (None, ""):
        parts.append(f"Style strength: {strength}; keep brand/product truth stronger than style transfer.")
    roles = capsule.get("reference_roles") if isinstance(capsule.get("reference_roles"), dict) else {}
    if roles:
        role_bits = [f"{key}: {value}" for key, value in roles.items() if str(value or "").strip()]
        if role_bits:
            parts.append("Reference roles: " + "; ".join(role_bits[:5]) + ".")
    if positive:
        parts.append("Use terms: " + "; ".join(positive[:5]) + ".")
    if negative:
        parts.append("Avoid style failures: " + "; ".join(negative[:7]) + ".")
    return " ".join(parts)


def promote_aesthetic_learning(
    brand_dir: Path,
    *,
    capsule_id: str | None = None,
    material_type: str | None = None,
    sentiment: str = "like",
    note: str = "",
) -> dict[str, Any]:
    prefs = load_aesthetic_preferences(brand_dir)
    sentiment = str(sentiment or "like").strip().lower()
    capsule = get_aesthetic_capsule(capsule_id) if capsule_id else None
    normalized_material = normalize_material_key(material_type)
    note = str(note or "").strip()
    entry = {
        "capsule_id": (capsule or {}).get("id") or str(capsule_id or "").strip(),
        "material_type": normalized_material,
        "note": note,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if sentiment in {"dislike", "reject", "negative"}:
        bucket = prefs.setdefault("style_dislikes", [])
        if entry not in bucket:
            bucket.append(entry)
        if entry["capsule_id"] and entry["capsule_id"] not in prefs.setdefault("negative_capsules", []):
            prefs["negative_capsules"].append(entry["capsule_id"])
        status = "negative_recorded"
    else:
        bucket = prefs.setdefault("style_likes", [])
        if entry not in bucket:
            bucket.append(entry)
        if entry["capsule_id"] and entry["capsule_id"] not in prefs.setdefault("preferred_capsules", []):
            prefs["preferred_capsules"].append(entry["capsule_id"])
        if normalized_material and entry["capsule_id"]:
            prefs.setdefault("selected_by_material", {})[normalized_material] = entry["capsule_id"]
        status = "positive_recorded"
    path = save_aesthetic_preferences(brand_dir, prefs)
    return {"status": status, "entry": entry, "path": str(path), "preferences": prefs}
