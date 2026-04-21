from __future__ import annotations

import json
import sys
from pathlib import Path

from .runtime_brand import load_material_policy
from .runtime_paths import SCRIPT_DIR

MODELS = json.loads((SCRIPT_DIR / "models.json").read_text())

SUPPORTED_IMAGE_EXTS = {".png", ".webp", ".svg", ".jpg", ".jpeg", ".gif", ".bmp"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".m4v"}
SUPPORTED_MEDIA_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_VIDEO_EXTS

# ── Material policy loaded from data/material_policy.json ────────────
# JSON overlay with hardcoded fallbacks — config file is optional.
_mp = load_material_policy()
MATERIAL_CONFIG = _mp.get("material_config", {})
COPY_BEARING_MATERIALS = set(_mp.get("classifications", {}).get("copy_bearing", []))

INSPIRE_URLS = {
    "symbol": "https://logosystem.co/symbol",
    "wordmark": "https://logosystem.co/wordmark",
    "symbol-text": "https://logosystem.co/symbol-and-text",
    "brown": "https://logosystem.co/color/brown",
    "beige": "https://logosystem.co/color/beige",
    "black": "https://logosystem.co/color/black",
    "all": "https://logosystem.co/",
}

SOCIAL_SPECS = _mp.get("social_specs", {})
MATERIAL_PROMPT_SNIPPET_ALIASES = _mp.get("snippet_aliases", {})
NON_INTERFACE_MATERIAL_KEYS = set(_mp.get("classifications", {}).get("non_interface", []))
INTERFACE_MATERIAL_KEYS = set(_mp.get("classifications", {}).get("interface", []))

REFERENCE_ANALYSIS_VERSION = 1

ROLE_PACK_TAG_PRIORITY = _mp.get("role_pack_tag_priority", [])
ROLE_TRANSLATION_DEFAULTS = _mp.get("role_translation_defaults", {})
MATERIAL_BRAND_POLICIES = _mp.get("brand_policies", {})
MATERIAL_SET_TEMPLATES = _mp.get("set_templates", {})


def normalize_material_type(material_type: str) -> str:
    key = (material_type or "logo").strip().lower()
    if key not in MATERIAL_CONFIG:
        available = ", ".join(sorted(MATERIAL_CONFIG))
        print(f"ERROR: Unknown material type '{material_type}'.", file=sys.stderr)
        print(f"Available: {available}", file=sys.stderr)
        sys.exit(1)
    return key


def resolve_learned_model(
    material_type: str,
    brand_dir: Path | None,
) -> str | None:
    """Return the learned winning model for `material_type`, or None.

    Reads the brand's `learnings.json` and matches the most recent
    `modelPreferences` entry whose `material_type` aliases to the
    requested type. "recraft-v4 + with refs" style text is parsed for
    the model token; the first valid model id wins. Accepts both the
    hyphen and underscore forms of material_type since legacy learnings
    may use either.

    This promotes learned winning setups into the default-model path so
    callers that do NOT pass --model automatically benefit from the
    brand's best-known model, rather than being stuck with the
    static material_config default.
    """
    if not brand_dir:
        return None
    learnings_path = Path(brand_dir) / "learnings.json"
    if not learnings_path.exists():
        return None
    try:
        data = json.loads(learnings_path.read_text())
    except Exception:
        return None
    prefs = data.get("modelPreferences") or []
    if not prefs:
        return None

    target_keys = {material_type, material_type.replace("-", "_"), material_type.replace("_", "-")}
    # Match the most recent preference for the requested material (entries are appended in order).
    matched = [p for p in prefs if (p.get("material_type") or "") in target_keys]
    if not matched:
        return None
    latest = matched[-1]
    text = str(latest.get("text") or "")
    # Extract the model name — stored as "Winning setup: <mode> + <model> + ..."
    for token in text.replace(",", " ").split():
        if token in MODELS.get("image", {}) or token in MODELS.get("video", {}):
            return token
    return None


def resolve_generation_mode(material_type: str, requested_mode: str) -> str:
    if requested_mode != "auto":
        return requested_mode
    return MATERIAL_CONFIG[material_type]["generation_mode"]


def resolve_default_model(
    material_type: str,
    generation_mode: str,
    workflow_mode: str,
    reference_paths: list[Path],
    material_prompt_key: str = "",
    has_motion_reference: bool = False,
    has_base_image: bool = False,
) -> str:
    if generation_mode == "video" and has_motion_reference:
        return "kling-v2.6-motion-control"
    # When editing/overlaying on a base image:
    # - Interface materials (browser-illustration, etc.) use nano-banana-2 for better
    #   text fidelity and UI preservation (flux-2-pro degrades text quality)
    # - Other materials use flux-2-pro for multi-ref editing
    _INTERFACE_TYPES = {"browser_illustration", "landing_hero", "product_banner", "feature_illustration"}
    if generation_mode == "image" and has_base_image:
        material_key = material_type.replace("-", "_")
        if material_key in _INTERFACE_TYPES:
            return "nano-banana-2"
        return "flux-2-pro"
    if generation_mode == "image" and reference_paths and workflow_mode in {"reference", "hybrid"}:
        if material_type in COPY_BEARING_MATERIALS:
            return "flux-2-flex"
        return "nano-banana-2"
    if material_type in {"pattern-system", "motif-system", "sticker-family", "badge-family", "icon-family"}:
        return MATERIAL_CONFIG[material_type]["default_model"]
    return MATERIAL_CONFIG[material_type]["default_model"]


def model_supports_reference_images(model_config: dict, generation_mode: str) -> bool:
    field_map = model_config.get("field_map") or {}
    if generation_mode == "image":
        return bool(field_map.get("image"))
    return bool(field_map.get("start_image"))


def model_supports_reference_tags(model_config: dict) -> bool:
    field_map = model_config.get("field_map") or {}
    return bool(field_map.get("image_tags"))


def model_supports_motion_reference(model_config: dict) -> bool:
    field_map = model_config.get("field_map") or {}
    return bool(field_map.get("motion_reference"))


def recommend_text_model(
    critique: dict,
    current_model: str,
    material_type: str,
    has_reference_images: bool,
) -> str | None:
    """Return a model recommendation if critique indicates text issues, else None."""
    text_accuracy = critique.get("text_accuracy", 1.0)
    text_issues = critique.get("text_issues") or []
    p1_text = [p for p in (critique.get("p1") or []) if any(
        kw in str(p).lower() for kw in ["text", "spell", "typo", "copy", "garble", "font"]
    )]
    if not (text_accuracy < 0.8 or text_issues or p1_text):
        return None
    if has_reference_images:
        return "flux-2-flex" if current_model != "flux-2-flex" else None
    return "ideogram" if current_model != "ideogram" else None


def resolve_default_aspect_ratio(material_type: str, requested_aspect_ratio: str | None, model_config: dict) -> str:
    if requested_aspect_ratio:
        return requested_aspect_ratio
    material_default = MATERIAL_CONFIG.get(material_type, {}).get("default_aspect_ratio")
    if material_default:
        return material_default
    return model_config.get("defaults", {}).get("aspect_ratio", "")


def infer_material_type_from_filename(filename: str) -> str:
    lower = filename.lower()
    for key in [
        "logo-animation",
        "feature-animation",
        "short-video",
        "motion-loop",
        "landing-hero",
        "product-banner",
        "hero-banner",
        "browser-illustration",
        "feature-illustration",
        "device-mockup",
        "lifestyle-mockup",
        "billboard-mockup",
        "product-visual",
        "linkedin-feed-portrait",
        "linkedin-feed-square",
        "linkedin-feed",
        "linkedin-card",
        "podcast-banner",
        "podcast-cover",
        "x-feed-portrait",
        "x-feed-square",
        "x-feed",
        "x-card",
        "og-card",
        "banner",
        "poster",
        "wordmark",
        "icon",
        "social",
        "gif",
        "animation",
        "lockup",
    ]:
        if key in lower:
            return key
    suffix = Path(filename).suffix.lower()
    if suffix in SUPPORTED_VIDEO_EXTS:
        return "short-video"
    return "logo"


def role_pack_material_key(material_type: str | None) -> str | None:
    if material_type is None:
        return None
    key = (material_type or "").strip().lower()
    if not key:
        return None
    normalized = key.replace("_", "-")
    return MATERIAL_PROMPT_SNIPPET_ALIASES.get(normalized) or normalized.replace("-", "_")


def list_material_types() -> None:
    print("Available material types:\n")
    for key, config in sorted(MATERIAL_CONFIG.items()):
        ratio = config.get("default_aspect_ratio", "—")
        print(f"  {key:<20} {config['generation_mode']:<6} default model: {config['default_model']:<12} default AR: {ratio}")
