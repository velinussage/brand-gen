from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from .runtime_io import warn
from .runtime_support import dedupe_keep_order

try:
    from .vlm_critique import REFERENCE_ANALYSIS_SYSTEM, run_vlm_json
except ImportError:  # pragma: no cover
    from vlm_critique import REFERENCE_ANALYSIS_SYSTEM, run_vlm_json

REFERENCE_ANALYSIS_VERSION = 1


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _weighted_majority(values: list[tuple[str, float]], default: str = "") -> str:
    weights: dict[str, float] = {}
    display: dict[str, str] = {}
    for raw_value, weight in values:
        text = str(raw_value or "").strip()
        if not text:
            continue
        key = text.lower()
        weights[key] = weights.get(key, 0.0) + float(weight)
        display.setdefault(key, text)
    if not weights:
        return default
    winner = max(weights.items(), key=lambda item: item[1])[0]
    return display.get(winner, default)


def _token_frequency_ranked(values: list[tuple[str, float]], *, limit: int = 6, minimum_weight: float = 0.0) -> list[str]:
    weights: dict[str, float] = {}
    display: dict[str, str] = {}
    for raw_value, weight in values:
        text = str(raw_value or "").strip()
        if not text:
            continue
        key = text.lower()
        weights[key] = weights.get(key, 0.0) + float(weight)
        display.setdefault(key, text)
    ranked = sorted(weights.items(), key=lambda item: item[1], reverse=True)
    out: list[str] = []
    for key, weight in ranked:
        if weight < minimum_weight:
            continue
        out.append(display[key])
        if len(out) >= limit:
            break
    return out


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        return None
    return tuple(int(text[idx:idx + 2], 16) for idx in range(0, 6, 2))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(value))) for value in rgb[:3]])


def _palette_temperature(colors: list[str]) -> str:
    warm = cool = 0
    for color in colors[:6]:
        rgb = _hex_to_rgb(color)
        if not rgb:
            continue
        r, g, b = rgb
        if r >= b + 18:
            warm += 1
        elif b >= r + 18:
            cool += 1
    if warm >= cool + 2:
        return "warm"
    if cool >= warm + 2:
        return "cool"
    return "neutral"


def _image_content_signature(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def sentence_join(items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def reference_analysis_mode(reference_analysis: dict) -> str:
    if not isinstance(reference_analysis, dict):
        return "unavailable"
    per_image = list(reference_analysis.get("per_image") or [])
    if not per_image:
        return "unavailable"
    if any(bool(item.get("vlm_available")) for item in per_image):
        return "vlm_augmented"
    return "deterministic_only"


def reference_analysis_confidence(reference_analysis: dict) -> str:
    if not isinstance(reference_analysis, dict):
        return "low"
    consistency = float(reference_analysis.get("consistency_score", 0.0) or 0.0)
    mode = reference_analysis_mode(reference_analysis)
    if mode == "unavailable":
        return "low"
    if mode == "deterministic_only":
        return "medium" if consistency >= 0.6 else "low"
    if consistency >= 0.72:
        return "high"
    if consistency >= 0.45:
        return "medium"
    return "low"


def extract_reference_image_stats(image_path: Path) -> dict:
    try:
        from PIL import Image, ImageStat, UnidentifiedImageError
    except ImportError:
        return {
            "dominant_colors": [],
            "brightness_label": "",
            "contrast_label": "",
            "aspect_ratio": "",
            "texture_patterns": [],
            "spatial_rhythm": "",
        }
    try:
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        ratio = round(width / max(height, 1), 2)
        stat = ImageStat.Stat(image)
        means = tuple(int(v) for v in stat.mean[:3])
        stddev = stat.stddev[:3]
        avg_brightness = sum(means) / 3
        avg_contrast = sum(stddev) / 3
        small = image.resize((64, 64))
        palette_image = small.convert("P", palette=Image.Palette.ADAPTIVE, colors=6)
        palette = palette_image.getpalette() or []
        color_counts = sorted(palette_image.getcolors() or [], reverse=True)
        dominant_colors = []
        for _, idx in color_counts[:6]:
            offset = idx * 3
            if offset + 2 < len(palette):
                dominant_colors.append(_rgb_to_hex((palette[offset], palette[offset + 1], palette[offset + 2])))
        brightness_label = "bright" if avg_brightness >= 190 else "mid" if avg_brightness >= 110 else "dark"
        contrast_label = "high" if avg_contrast >= 60 else "medium" if avg_contrast >= 35 else "low"
        texture_patterns = []
        if contrast_label == "low":
            texture_patterns.append("smooth")
        if contrast_label == "high":
            texture_patterns.append("high-contrast")
        spatial_rhythm = "structured" if 0.8 <= ratio <= 1.8 else "wide" if ratio > 1.8 else "tall"
        return {
            "dominant_colors": dominant_colors,
            "brightness_label": brightness_label,
            "contrast_label": contrast_label,
            "aspect_ratio": spatial_rhythm,
            "texture_patterns": texture_patterns,
            "spatial_rhythm": spatial_rhythm,
        }
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        warn(f"Reference analysis fell back to empty stats for {image_path}: {exc}")
        return {
            "dominant_colors": [],
            "brightness_label": "",
            "contrast_label": "",
            "aspect_ratio": "",
            "texture_patterns": [],
            "spatial_rhythm": "",
        }


def build_reference_analysis_inputs(reference_paths: list[Path], role_pack_roles: list[dict]) -> list[dict]:
    role_lookup: dict[str, dict] = {}
    for item in role_pack_roles or []:
        path = str(item.get("path") or "").strip()
        if path:
            role_lookup[str(Path(path).expanduser().resolve())] = item
    out: list[dict] = []
    for idx, path in enumerate(reference_paths or []):
        if not path.exists():
            continue
        resolved = path.expanduser().resolve()
        role_item = role_lookup.get(str(resolved)) or {}
        role = str(role_item.get("role") or "").strip()
        bucket = "product" if idx == 0 else "inspiration"
        out.append(
            {
                "path": resolved,
                "role": role or ("product" if bucket == "product" else "reference"),
                "bucket": bucket,
                "source_key": str(role_item.get("source_key") or ""),
                "source_name": str(role_item.get("source_name") or ""),
            }
        )
    return out


def _reference_analysis_stub(item: dict, deterministic: dict, reason: str) -> dict:
    return {
        "path": str(item["path"]),
        "role": item.get("role") or "",
        "bucket": item.get("bucket") or "",
        "source_key": item.get("source_key") or "",
        "source_name": item.get("source_name") or "",
        "dominant_colors": deterministic.get("dominant_colors") or [],
        "lighting_style": deterministic.get("brightness_label") or "",
        "composition": deterministic.get("aspect_ratio") or "",
        "typography_cues": [],
        "texture_patterns": deterministic.get("texture_patterns") or [],
        "spatial_rhythm": deterministic.get("spatial_rhythm") or "",
        "mood_keywords": [],
        "notable_elements": [],
        "transferable_mechanics": [],
        "role_relevance": "unknown",
        "confidence": 0.0,
        "vlm_available": False,
        "vlm_unavailable_reason": reason,
        "deterministic": deterministic,
    }


def run_vlm_reference_analysis(item: dict, brand_context: str, *, env: dict | None = None) -> dict:
    image_path = Path(item["path"])
    deterministic = extract_reference_image_stats(image_path)
    bucket = item.get("bucket") or "reference"
    role = item.get("role") or bucket
    focus = (
        "Treat this as product truth. Extract actual palette, typography, component cues, and proof-bearing UI patterns that should remain truthful."
        if bucket == "product"
        else "Treat this as inspiration. Extract transferable mechanics only: composition, spacing rhythm, texture treatment, framing, and presentation logic. Do not treat foreign logos or copy as brand truth."
    )
    user_text = (
        f"## Role\n{role}\n\n"
        f"## Bucket\n{bucket}\n\n"
        f"## Brand context\n{brand_context[:1200]}\n\n"
        f"## Deterministic cues\n"
        f"Dominant colors: {', '.join(deterministic.get('dominant_colors') or []) or 'n/a'}\n"
        f"Brightness: {deterministic.get('brightness_label') or 'n/a'}\n"
        f"Contrast: {deterministic.get('contrast_label') or 'n/a'}\n"
        f"Aspect ratio: {deterministic.get('aspect_ratio') or 'n/a'}\n"
        f"Spatial rhythm: {deterministic.get('spatial_rhythm') or 'n/a'}\n\n"
        f"{focus}\n\n"
        "Return JSON only with keys: composition, lighting_style, typography_cues, texture_patterns, "
        "spatial_rhythm, mood_keywords, notable_elements, transferable_mechanics, role_relevance, confidence."
    )
    parsed = run_vlm_json(image_path, REFERENCE_ANALYSIS_SYSTEM, user_text, env=env, max_tokens=700)
    if parsed is None:
        return _reference_analysis_stub(
            item,
            deterministic,
            "No VLM API key available (set OPENROUTER_API_KEY or ANTHROPIC_API_KEY) or response was invalid",
        )
    return {
        "path": str(image_path),
        "role": role,
        "bucket": bucket,
        "source_key": item.get("source_key") or "",
        "source_name": item.get("source_name") or "",
        "dominant_colors": deterministic.get("dominant_colors") or [],
        "lighting_style": str(parsed.get("lighting_style") or deterministic.get("brightness_label") or "").strip(),
        "composition": str(parsed.get("composition") or deterministic.get("aspect_ratio") or "").strip(),
        "typography_cues": dedupe_keep_order([str(value).strip() for value in (parsed.get("typography_cues") or []) if str(value).strip()][:6]),
        "texture_patterns": dedupe_keep_order(
            [str(value).strip() for value in (deterministic.get("texture_patterns") or []) if str(value).strip()]
            + [str(value).strip() for value in (parsed.get("texture_patterns") or []) if str(value).strip()]
        )[:6],
        "spatial_rhythm": str(parsed.get("spatial_rhythm") or deterministic.get("spatial_rhythm") or "").strip(),
        "mood_keywords": dedupe_keep_order([str(value).strip() for value in (parsed.get("mood_keywords") or []) if str(value).strip()][:6]),
        "notable_elements": dedupe_keep_order([str(value).strip() for value in (parsed.get("notable_elements") or []) if str(value).strip()][:8]),
        "transferable_mechanics": dedupe_keep_order([str(value).strip() for value in (parsed.get("transferable_mechanics") or []) if str(value).strip()][:8]),
        "role_relevance": str(parsed.get("role_relevance") or "").strip() or "medium",
        "confidence": _clamp(_safe_float(parsed.get("confidence"), 0.65)),
        "vlm_available": True,
        "vlm_provider": parsed.get("vlm_provider") or "",
        "deterministic": deterministic,
    }


def aggregate_reference_dna(analyses: list[dict], reference_inputs: list[dict], *, reference_set_hash: str) -> dict:
    role_weights = {"product": 2.0, "inspiration": 1.0, "reference": 1.0}
    product_items = [item for item in analyses if item.get("bucket") == "product"]
    inspiration_items = [item for item in analyses if item.get("bucket") == "inspiration"]
    all_items = list(analyses)

    def weighted_tokens(items: list[dict], field: str, *, limit: int = 6) -> list[str]:
        values: list[tuple[str, float]] = []
        for item in items:
            weight = role_weights.get(item.get("bucket") or "reference", 1.0) * max(_safe_float(item.get("confidence"), 0.3), 0.25)
            raw_values = item.get(field) or []
            if isinstance(raw_values, str):
                raw_values = [raw_values]
            for value in raw_values:
                values.append((str(value), weight))
        return _token_frequency_ranked(values, limit=limit)

    def weighted_majority_field(items: list[dict], field: str, default: str = "") -> str:
        values: list[tuple[str, float]] = []
        for item in items:
            weight = role_weights.get(item.get("bucket") or "reference", 1.0) * max(_safe_float(item.get("confidence"), 0.3), 0.25)
            raw = str(item.get(field) or "").strip()
            if raw:
                values.append((raw, weight))
        return _weighted_majority(values, default)

    palette_votes: list[tuple[str, float]] = []
    for item in product_items or all_items:
        weight = role_weights.get(item.get("bucket") or "reference", 1.0) * max(_safe_float(item.get("confidence"), 0.4), 0.25)
        for color in (item.get("dominant_colors") or [])[:4]:
            palette_votes.append((str(color), weight))

    product_palette = _token_frequency_ranked(palette_votes, limit=6)
    inspiration_palette = _token_frequency_ranked(
        [(str(color), max(_safe_float(item.get("confidence"), 0.3), 0.25)) for item in inspiration_items for color in (item.get("dominant_colors") or [])[:4]],
        limit=6,
    )

    available_flags = [1.0 if item.get("vlm_available") else 0.0 for item in analyses]
    confidence_values = [_safe_float(item.get("confidence"), 0.0) for item in analyses]
    consistency_basis = []
    for field in ("composition", "spatial_rhythm", "lighting_style"):
        values = [str(item.get(field) or "").strip().lower() for item in analyses if str(item.get(field) or "").strip()]
        if values:
            top = max(values.count(value) for value in set(values))
            consistency_basis.append(top / len(values))
    consistency_basis.append(_average(available_flags))
    consistency_basis.append(_average(confidence_values))
    consistency_score = round(_clamp(_average(consistency_basis)), 2) if consistency_basis else 0.0

    warnings: list[str] = []
    if len(analyses) >= 2 and consistency_score < 0.45:
        warnings.append("Reference set pulls in multiple directions; keep inspiration translated and favor the product-truth refs.")
    if not product_items:
        warnings.append("No product-truth refs detected; observed palette/mechanics are advisory only.")
    product_temp = _palette_temperature(product_palette)
    inspiration_temp = _palette_temperature(inspiration_palette)
    if product_items and inspiration_items and product_temp != "neutral" and inspiration_temp != "neutral" and product_temp != inspiration_temp:
        warnings.append(f"Inspiration refs skew {inspiration_temp} while product refs skew {product_temp}; treat inspiration as mechanics, not palette truth.")

    product_observations = {
        "palette": product_palette,
        "palette_confidence": round(_clamp(0.45 + 0.15 * len(product_items) + 0.25 * consistency_score), 2) if product_items else 0.0,
        "typography_cues": weighted_tokens(product_items, "typography_cues", limit=6),
        "component_cues": weighted_tokens(product_items, "notable_elements", limit=6),
        "mood_keywords": weighted_tokens(product_items, "mood_keywords", limit=5),
        "lighting_style": weighted_majority_field(product_items, "lighting_style"),
    }
    inspiration_observations = {
        "mechanics": weighted_tokens(inspiration_items, "transferable_mechanics", limit=6),
        "composition_patterns": weighted_tokens(inspiration_items, "composition", limit=4),
        "texture_patterns": weighted_tokens(inspiration_items, "texture_patterns", limit=6),
        "mood_keywords": weighted_tokens(inspiration_items, "mood_keywords", limit=5),
        "palette": inspiration_palette,
    }

    aggregated = {
        "schema_type": "reference_analysis",
        "schema_version": REFERENCE_ANALYSIS_VERSION,
        "reference_set_hash": reference_set_hash,
        "source_count": len(reference_inputs),
        "product_observations": product_observations,
        "inspiration_observations": inspiration_observations,
        "consistency_score": consistency_score,
        "warnings": warnings,
        "per_image": analyses,
    }
    aggregated["reference_analysis_mode"] = reference_analysis_mode(aggregated)
    aggregated["reference_analysis_confidence"] = reference_analysis_confidence(aggregated)
    return aggregated


def build_reference_analysis_snippet(
    reference_analysis: dict,
    material_type: str | None = None,
    *,
    role_pack_material_key_fn: Callable[[str | None], str | None] | None = None,
) -> str:
    if not isinstance(reference_analysis, dict):
        return ""
    if role_pack_material_key_fn is None:
        from .runtime_models import role_pack_material_key

        role_pack_material_key_fn = role_pack_material_key
    product = reference_analysis.get("product_observations") or {}
    inspiration = reference_analysis.get("inspiration_observations") or {}
    warnings = reference_analysis.get("warnings") or []
    mode = reference_analysis_mode(reference_analysis)
    confidence = reference_analysis_confidence(reference_analysis)
    lines: list[str] = []
    palette = product.get("palette") or []
    palette_confidence = float(product.get("palette_confidence") or 0.0)
    if palette and palette_confidence >= 0.45:
        lines.append("Observed product refs reinforce palette around " + ", ".join(str(color) for color in palette[:4]) + ".")
    mechanics = inspiration.get("mechanics") or []
    if mechanics:
        lines.append("Observed inspiration refs suggest transferable mechanics such as " + sentence_join([str(item) for item in mechanics[:3]]) + ".")
    composition_patterns = inspiration.get("composition_patterns") or []
    if composition_patterns and role_pack_material_key_fn(material_type) in {"browser_illustration", "landing_hero", "product_banner", "feature_illustration"}:
        lines.append("Presentation framing cues from refs: " + sentence_join([str(item) for item in composition_patterns[:2]]) + ".")
    if mode == "deterministic_only":
        lines.append(f"Reference-analysis caveat: observations are deterministic-only and confidence is {confidence}.")
    if warnings:
        lines.append("Reference-analysis caution: " + str(warnings[0]))
    return "\n".join(lines).strip()


def reference_analysis_review_notes(reference_analysis: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    recommendations: list[str] = []
    if not isinstance(reference_analysis, dict):
        return issues, recommendations
    consistency = float(reference_analysis.get("consistency_score") or 0.0)
    mode = reference_analysis_mode(reference_analysis)
    confidence = reference_analysis_confidence(reference_analysis)
    warnings = [str(item).strip() for item in (reference_analysis.get("warnings") or []) if str(item).strip()]
    if consistency and consistency < 0.45:
        issues.append("Reference set is visually inconsistent; the prompt should favor one clear product-truth path.")
        recommendations.append("Reduce the number of conflicting references or explicitly state which refs only control framing.")
    if mode == "deterministic_only":
        recommendations.append(
            f"Reference analysis is deterministic-only (confidence: {confidence}); keep reference-role translations approximate and preserve product-truth refs."
        )
    for warning in warnings[:2]:
        if warning not in recommendations:
            recommendations.append(warning)
    return issues, recommendations


def ensure_reference_analysis(
    brand_dir: Path,
    *,
    profile: dict,
    identity: dict,
    reference_paths: list[Path],
    role_pack_roles: list[dict],
    material_type: str | None = None,
    skip_extraction: bool = False,
    refresh_extraction: bool = False,
    load_blackboard_fn: Callable[..., dict] | None = None,
    save_blackboard_fn: Callable[..., Path] | None = None,
    append_blackboard_decision_fn: Callable[..., dict] | None = None,
    summarize_identity_fn: Callable[[dict, dict], dict] | None = None,
    role_pack_material_key_fn: Callable[[str | None], str | None] | None = None,
    env: dict | None = None,
) -> dict:
    if load_blackboard_fn is None or save_blackboard_fn is None or append_blackboard_decision_fn is None:
        from .blackboard import append_blackboard_decision, load_blackboard, save_blackboard

        load_blackboard_fn = load_blackboard_fn or load_blackboard
        save_blackboard_fn = save_blackboard_fn or save_blackboard
        append_blackboard_decision_fn = append_blackboard_decision_fn or append_blackboard_decision
    if summarize_identity_fn is None:
        from .material_planning import summarize_identity

        summarize_identity_fn = summarize_identity
    if role_pack_material_key_fn is None:
        from .runtime_models import role_pack_material_key

        role_pack_material_key_fn = role_pack_material_key
    reference_inputs = build_reference_analysis_inputs(reference_paths, role_pack_roles)
    if not reference_inputs:
        return {}
    board = load_blackboard_fn(brand_dir, profile, identity)
    existing = board.get("reference_analysis") or {}
    signature_parts = [f"{item['role']}|{item['bucket']}|{item['path']}|{_image_content_signature(item['path'])}" for item in reference_inputs]
    signature_parts.append(f"material:{role_pack_material_key_fn(material_type)}")
    reference_set_hash = hashlib.sha256("\n".join(signature_parts).encode("utf-8")).hexdigest()[:20]
    if not refresh_extraction and existing.get("reference_set_hash") == reference_set_hash and existing.get("schema_version") == REFERENCE_ANALYSIS_VERSION:
        return existing
    if skip_extraction:
        return {}

    summary = summarize_identity_fn(profile, identity)
    brand_context = (
        f"Brand: {summary.get('brand_name') or 'n/a'}\n"
        f"Summary: {summary.get('summary') or 'n/a'}\n"
        f"Palette direction: {', '.join(summary.get('palette_direction') or []) or 'n/a'}\n"
        f"Typography cues: {', '.join(summary.get('typography_cues') or []) or 'n/a'}\n"
        f"Typography roles: {', '.join(f'{v} ({k})' for k, v in (summary.get('typography_roles') or {}).items()) or 'n/a'}\n"
        f"Approved devices: {', '.join(summary.get('approved_graphic_devices') or []) or 'n/a'}"
    )
    analyses = [run_vlm_reference_analysis(item, brand_context, env=env) for item in reference_inputs]
    aggregated = aggregate_reference_dna(analyses, reference_inputs, reference_set_hash=reference_set_hash)
    board["reference_analysis"] = aggregated
    append_blackboard_decision_fn(
        board,
        agent="brand_director",
        decision=f"Auto-extracted reference analysis from {len(reference_inputs)} refs.",
        confidence=0.66 if any(item.get("vlm_available") for item in analyses) else 0.42,
        severity="P2" if (aggregated.get("warnings") or []) else "P3",
        data={"reference_set_hash": reference_set_hash, "material_type": material_type or ""},
    )
    save_blackboard_fn(brand_dir, board)
    return aggregated


def check_inspiration_pipeline_status(
    brand_gen_dir: Path | None,
    active_brand: str | None,
    workflow_mode: str | None,
    *,
    resolve_active_brand_key_fn: Callable[..., str | None] | None = None,
) -> dict:
    repo_root = Path(__file__).resolve().parent.parent
    if resolve_active_brand_key_fn is None:
        from .session import resolve_active_brand_key

        resolve_active_brand_key_fn = resolve_active_brand_key
    resolved = brand_gen_dir
    brand_key = active_brand
    if not brand_key and resolved:
        try:
            brand_key = resolve_active_brand_key_fn(brand_gen_dir=resolved, repo_root=repo_root)
        except TypeError:
            brand_key = resolve_active_brand_key_fn(resolved)
    warnings: list[str] = []
    suggestions: list[str] = []

    if workflow_mode not in ("hybrid", "inspiration"):
        return {"ok": True, "warnings": [], "suggestions": [], "mode": workflow_mode or "reference"}

    if not resolved or not brand_key:
        warnings.append("No .brand-gen workspace or active brand found; inspiration pipeline cannot load.")
        suggestions.append("Run: bgen init --brand-name <name>")
        return {"ok": False, "warnings": warnings, "suggestions": suggestions, "mode": workflow_mode}

    brand_dir = resolved / "brands" / brand_key
    inspirations_path = brand_dir / "inspirations.json"
    if not inspirations_path.exists():
        warnings.append(f"Brand '{brand_key}' has no inspiration sources configured.")
        suggestions.append(f"Run: bgen inspire {brand_key} --sources <source1,source2>")
        return {"ok": False, "warnings": warnings, "suggestions": suggestions, "mode": workflow_mode}

    try:
        import json
        payload = json.loads(inspirations_path.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        warnings.append("Configured inspiration sources could not be read.")
        suggestions.append(f"Inspect: {inspirations_path}")
        return {"ok": False, "warnings": warnings, "suggestions": suggestions, "mode": workflow_mode}

    raw_sources = payload.get("sources") or []
    if isinstance(raw_sources, dict):
        sources = []
        for key, value in raw_sources.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("key", key)
                sources.append(item)
            else:
                sources.append({"key": str(key), "source": value})
    else:
        sources = []
        if isinstance(raw_sources, list):
            for item in raw_sources:
                if isinstance(item, dict):
                    sources.append(item)
                else:
                    sources.append({"key": str(item), "source": str(item)})

    if not sources:
        warnings.append(f"Brand '{brand_key}' has no inspiration sources configured.")
        suggestions.append(f"Run: bgen inspire {brand_key} --sources <source1,source2>")
    if workflow_mode == "inspiration" and not payload.get("enabled", False):
        warnings.append("inspirationMode is off for an inspiration-mode workflow.")
        suggestions.append("Run: bgen inspiration-mode on")

    pending = []
    inspiration_root = resolved / "inspiration"
    for source in sources:
        source_key = str(source.get("key") or source.get("source") or "").strip()
        if not source_key:
            continue
        category = str(source.get("category") or "").strip()
        candidate_dirs = []
        if category:
            candidate_dirs.append(inspiration_root / category / source_key / ".design-memory")
        else:
            candidate_dirs.append(inspiration_root / source_key / ".design-memory")
            if inspiration_root.exists():
                candidate_dirs.extend(inspiration_root.glob(f"*/{source_key}/.design-memory"))
        if not any(dm_dir.exists() for dm_dir in candidate_dirs):
            pending.append(source_key)
    if pending:
        warnings.append("Inspiration sources are configured but not extracted yet: " + ", ".join(pending[:4]))
        suggestions.append("Run: bgen extract-inspiration --category <category> --sources " + ",".join(pending[:4]))

    return {"ok": not warnings, "warnings": warnings, "suggestions": suggestions, "mode": workflow_mode}
