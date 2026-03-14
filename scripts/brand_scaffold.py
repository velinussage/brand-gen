#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BRAND_PROFILE_TEMPLATE_PATH = REPO_ROOT / "data" / "brand-profile-template.json"
BRAND_REGISTRY_FILENAME = "index.json"


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower())
    return value.strip("-") or "brand"


def dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def parse_csv_values(*values: str | None) -> list[str]:
    out: list[str] = []
    for raw in values:
        if not raw:
            continue
        parts = [part.strip() for part in str(raw).replace("\n", ",").split(",")]
        out.extend(part for part in parts if part)
    return dedupe_keep_order(out)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def load_brand_profile_template() -> dict:
    template = read_json(BRAND_PROFILE_TEMPLATE_PATH)
    if template:
        return template
    return {
        "profile_version": 2,
        "brand_name": "Working Brand",
        "description": "",
        "homepage_url": "",
        "project_root": "",
        "keywords": [],
        "product_categories": [],
        "audiences": [],
        "color_candidates": [],
        "font_candidates": [],
        "radius_tokens": ["12px", "16px"],
        "logo_candidates": [],
        "brand_assets": {
            "icon": "",
            "wordmark": "",
            "lockup": "",
            "icon_candidates": [],
            "wordmark_candidates": [],
            "lockup_candidates": [],
            "allow_synthetic_lockup": False,
        },
        "identity": {
            "summary": "",
            "tone_words": [],
            "brand_anchors": [],
        },
        "brand_mark": {
            "anatomy": [],
            "approved_primitives": [],
            "approved_compositions": [],
            "forbidden_abstractions": [],
        },
        "design_language": {
            "semantic_palette_roles": [],
            "typography_cues": [],
            "shape_language": [],
            "component_cues": [],
            "framework_cues": [],
            "spacing_scale": [],
            "approved_graphic_devices": [],
            "forbidden_elements": [],
        },
        "messaging": {
            "tagline": "",
            "elevator": "",
            "voice": {"description": "", "tone_words": [], "do": [], "dont": []},
            "value_propositions": [],
            "approved_copy_bank": {"headlines": [], "slogans": [], "subheadlines": [], "cta_pairs": []},
        },
        "brand_guardrail_prelude": "",
    }


def deep_merge_defaults(payload: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(defaults)
    for key, value in (payload or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge_defaults(value, out[key])
        else:
            out[key] = value
    return out


def build_profile_from_brief(
    *,
    brand_name: str,
    brand_dir: Path,
    description: str = "",
    tone_words: list[str] | None = None,
    palette: list[str] | None = None,
    keywords: list[str] | None = None,
    homepage_url: str = "",
    voice_description: str = "",
    value_props: list[str] | None = None,
    profile: dict | None = None,
) -> dict:
    template = load_brand_profile_template()
    base = deep_merge_defaults(profile or {}, template)
    tones = dedupe_keep_order(tone_words or [])
    colors = dedupe_keep_order(palette or [])
    keyword_values = dedupe_keep_order((keywords or []) + tones)
    value_prop_values = dedupe_keep_order(value_props or [])

    base["profile_version"] = max(int(base.get("profile_version") or 1), 2)
    base["brand_name"] = brand_name
    if description:
        base["description"] = description.strip()
    base["project_root"] = str(brand_dir)
    if homepage_url:
        base["homepage_url"] = homepage_url.strip()
    if keyword_values:
        base["keywords"] = keyword_values
    if colors:
        base["color_candidates"] = colors
    if tones:
        identity = base.setdefault("identity", {})
        identity["tone_words"] = tones
        messaging = base.setdefault("messaging", {})
        voice = messaging.setdefault("voice", {})
        voice["tone_words"] = tones
    if description:
        identity = base.setdefault("identity", {})
        identity["summary"] = description.strip()
        messaging = base.setdefault("messaging", {})
        messaging.setdefault("elevator", description.strip())
    if voice_description:
        messaging = base.setdefault("messaging", {})
        voice = messaging.setdefault("voice", {})
        voice["description"] = voice_description.strip()
    if value_prop_values:
        messaging = base.setdefault("messaging", {})
        messaging["value_propositions"] = value_prop_values
    if colors:
        design_language = base.setdefault("design_language", {})
        existing_roles = design_language.get("semantic_palette_roles") or []
        if not existing_roles:
            role_names = ["primary", "secondary", "accent", "support"]
            design_language["semantic_palette_roles"] = [
                f"{role_names[idx]} {value}" for idx, value in enumerate(colors[: len(role_names)])
            ]
    if not base.get("radius_tokens"):
        base["radius_tokens"] = ["12px", "16px"]
    return base


def ensure_brand_structure(brand_dir: Path) -> None:
    brand_dir.mkdir(parents=True, exist_ok=True)
    for child in [
        "screenshots",
        "plans",
        "sets",
        "examples",
        "reviews",
        "references",
        "product-screens",
        "inspiration",
        "motion-references",
    ]:
        (brand_dir / child).mkdir(parents=True, exist_ok=True)


def get_brand_registry_path(brand_gen_dir: Path) -> Path:
    return brand_gen_dir / "brands" / BRAND_REGISTRY_FILENAME


def load_brand_registry(brand_gen_dir: Path) -> dict:
    registry = read_json(get_brand_registry_path(brand_gen_dir))
    if registry:
        return registry
    return {"version": 1, "brands": {}}


def register_brand(brand_gen_dir: Path, brand_key: str, payload: dict) -> dict:
    registry = load_brand_registry(brand_gen_dir)
    brands = registry.setdefault("brands", {})
    entry = dict(brands.get(brand_key) or {})
    entry.update({k: v for k, v in payload.items() if v not in (None, "")})
    brands[brand_key] = entry
    write_json(get_brand_registry_path(brand_gen_dir), registry)
    return registry
