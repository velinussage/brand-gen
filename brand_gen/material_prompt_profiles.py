"""Material prompt profile registry for brand-gen.

Profiles refine the generic material runtime config with prompt-facing
contracts: job-to-be-done, exact-text strategy, aesthetic capsule preferences,
reference roles, failure bans, and review focus.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .runtime_models import MATERIAL_CONFIG
from .runtime_paths import SCRIPT_DIR
from .scoring.rubric_registry import material_rubric_key

_PROFILES_PATH = SCRIPT_DIR.parent / "data" / "material_prompt_profiles.json"

_MATERIAL_ALIASES = {
    "x_card": "x-card",
    "x_feed": "x-feed",
    "x_feed_square": "x-feed-square",
    "x_feed_portrait": "x-feed-portrait",
    "linkedin_card": "linkedin-card",
    "linkedin_feed": "linkedin-feed",
    "linkedin_feed_square": "linkedin-feed-square",
    "linkedin_feed_portrait": "linkedin-feed-portrait",
    "announcement_card": "announcement-card",
    "carousel_slide": "carousel-slide",
    "proof_poster": "proof-poster",
    "campaign_poster": "proof-poster",
    "landing_hero": "landing-hero",
    "hero_banner": "hero-banner",
    "website_hero_illustration": "website-hero-illustration",
    "product_banner": "product-banner",
    "product_visual": "product-visual",
    "feature_illustration": "feature-illustration",
    "browser_illustration": "browser-illustration",
    "terminal_hero": "terminal-hero",
    "cli_recording": "cli-recording",
    "command_illustration": "command-illustration",
    "icon_family": "icon-family",
    "badge_family": "badge-family",
    "sticker_family": "sticker-family",
    "motif_system": "motif-system",
    "site_pattern_tile": "site-pattern-tile",
    "pattern_system": "site-pattern-tile",
    "pattern_board": "pattern-board",
    "merch_poster": "merch-poster",
    "content_card": "content-card",
    "content_card_square": "content-card-square",
    "editorial_card": "editorial-card",
    "system_explainer_illustration": "system-explainer-illustration",
    "concept_illustration": "system-explainer-illustration",
    "editorial_metaphor_illustration": "editorial-metaphor-illustration",
    "info_card": "info-card",
    "data_card": "data-card",
    "state_card": "state-card",
    "quote_card": "quote-card",
    "process_card": "process-card",
    "event_poster": "event-poster",
    "podcast_cover": "podcast-cover",
    "podcast_banner": "podcast-banner",
    "illustrated_brand_world": "illustrated-brand-world",
    "brand_scene": "illustrated-brand-world",
    "feature_animation": "feature-animation",
    "bumper_animation": "bumper-animation",
    "logo_animation": "logo-animation",
    "motion_loop": "motion-loop",
    "short_video": "short-video",
    "stinger_animation": "stinger-animation",
}


def normalize_material_profile_key(material_type: str | None) -> str:
    key = str(material_type or "").strip().lower().replace("_", "-")
    return _MATERIAL_ALIASES.get(key.replace("-", "_"), key)


def load_material_prompt_profiles() -> dict[str, Any]:
    if not _PROFILES_PATH.exists():
        return {"schema_version": 1, "batches": {}, "profiles": {}}
    data = json.loads(_PROFILES_PATH.read_text())
    if not isinstance(data, dict):
        return {"schema_version": 1, "batches": {}, "profiles": {}}
    data.setdefault("profiles", {})
    data.setdefault("batches", {})
    return data


def get_material_prompt_profile(material_type: str | None) -> dict[str, Any] | None:
    key = normalize_material_profile_key(material_type)
    if not key:
        return None
    profile = (load_material_prompt_profiles().get("profiles") or {}).get(key)
    return dict(profile) if isinstance(profile, dict) else None


def listed_material_profile_types() -> list[str]:
    data = load_material_prompt_profiles()
    out: list[str] = []
    for items in (data.get("batches") or {}).values():
        if isinstance(items, list):
            out.extend(str(item) for item in items)
    return out


def render_material_prompt_profile(profile: dict[str, Any] | None) -> str:
    if not isinstance(profile, dict) or not profile:
        return ""
    parts: list[str] = []
    job = str(profile.get("job_to_be_done") or "").strip()
    if job:
        parts.append(f"Material job: {job}")
    skeleton = str(profile.get("prompt_skeleton") or "").strip()
    if skeleton:
        parts.append(f"Prompt skeleton: {skeleton}")
    exact = profile.get("exact_text_policy") if isinstance(profile.get("exact_text_policy"), dict) else {}
    if exact:
        mode = str(exact.get("mode") or "").strip()
        guidance = str(exact.get("guidance") or "").strip()
        text = "; ".join(item for item in [mode, guidance] if item)
        if text:
            parts.append(f"Exact-text policy: {text}")
    roles = [str(item).strip() for item in (profile.get("allowed_reference_roles") or []) if str(item).strip()]
    if roles:
        parts.append("Allowed reference roles: " + ", ".join(roles) + ".")
    bans = [str(item).strip() for item in (profile.get("negative_prompt_failure_bans") or []) if str(item).strip()]
    if bans:
        parts.append("Material-specific failures to avoid: " + "; ".join(bans[:6]) + ".")
    focus = [str(item).strip() for item in (profile.get("review_focus") or []) if str(item).strip()]
    if focus:
        parts.append("Review focus: " + "; ".join(focus[:5]) + ".")
    web_delivery = profile.get("web_delivery") if isinstance(profile.get("web_delivery"), dict) else {}
    if web_delivery:
        delivery_parts = []
        if web_delivery.get("display_width") and web_delivery.get("display_height"):
            delivery_parts.append(f"{web_delivery['display_width']}x{web_delivery['display_height']}")
        if web_delivery.get("primary_file_type"):
            delivery_parts.append(f"primary {web_delivery['primary_file_type']}")
        if web_delivery.get("optional_alternate_file_type"):
            delivery_parts.append(f"optional {web_delivery['optional_alternate_file_type']}")
        if web_delivery.get("duration_seconds"):
            delivery_parts.append(f"{web_delivery['duration_seconds']}s loop")
        usage = str(web_delivery.get("html_usage") or "").strip()
        if usage:
            delivery_parts.append(usage)
        if delivery_parts:
            parts.append("Web delivery: " + "; ".join(delivery_parts) + ".")
    return " ".join(parts)


def validate_material_prompt_profiles(material_types: list[str] | None = None) -> list[str]:
    """Return validation errors for material prompt profile coverage."""
    from .aesthetic_curation import get_aesthetic_capsule

    data = load_material_prompt_profiles()
    profiles = data.get("profiles") or {}
    targets = material_types or listed_material_profile_types() or sorted(profiles)
    errors: list[str] = []
    valid_roles = {"composition", "motif", "application", "motion", "product_truth"}
    for raw in targets:
        material_type = normalize_material_profile_key(raw)
        profile = profiles.get(material_type)
        if material_type not in MATERIAL_CONFIG:
            errors.append(f"{material_type}: no runtime MATERIAL_CONFIG entry")
        if not isinstance(profile, dict):
            errors.append(f"{material_type}: missing prompt profile")
            continue
        for field in [
            "job_to_be_done",
            "default_aspect_ratio",
            "default_model",
            "default_render_backend",
            "exact_text_policy",
            "allowed_reference_roles",
            "prompt_skeleton",
            "negative_prompt_failure_bans",
            "review_focus",
            "review_rubric_key",
        ]:
            if profile.get(field) in (None, "", [], {}):
                errors.append(f"{material_type}: missing {field}")
        capsules = profile.get("best_aesthetic_capsules") or []
        fallback = str(profile.get("aesthetic_fallback") or "").strip()
        if not capsules and not fallback:
            errors.append(f"{material_type}: needs best_aesthetic_capsules or aesthetic_fallback")
        for capsule_id in capsules:
            if not get_aesthetic_capsule(str(capsule_id)):
                errors.append(f"{material_type}: unknown aesthetic capsule {capsule_id}")
        roles = set(str(item) for item in (profile.get("allowed_reference_roles") or []))
        unknown_roles = sorted(roles - valid_roles)
        if unknown_roles:
            errors.append(f"{material_type}: unknown reference roles {unknown_roles}")
        exact = profile.get("exact_text_policy") if isinstance(profile.get("exact_text_policy"), dict) else {}
        if not exact.get("mode") or not exact.get("guidance"):
            errors.append(f"{material_type}: unclear exact_text_policy")
        rubric = str(profile.get("review_rubric_key") or "")
        expected = material_rubric_key(material_type) or "universal"
        if rubric != expected:
            errors.append(f"{material_type}: review_rubric_key {rubric!r} != expected {expected!r}")
    return errors


__all__ = [
    "get_material_prompt_profile",
    "listed_material_profile_types",
    "load_material_prompt_profiles",
    "normalize_material_profile_key",
    "render_material_prompt_profile",
    "validate_material_prompt_profiles",
]
