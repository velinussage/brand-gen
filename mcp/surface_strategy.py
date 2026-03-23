from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_STRATEGY_PATH = Path(__file__).resolve().parent.parent / "data" / "artifact_surface_strategies.json"
_GOVERNED_ENTITY_TYPES = {"prompt", "skill", "library", "proposal", "community", "dao", "update"}


@dataclass(frozen=True)
class StrategyContext:
    material_type: str = ""
    entity_type: str = ""
    render_backend: str = "native"
    source_url: str = ""
    purpose: str = ""
    target_surface: str = ""
    product_truth_expression: str = ""
    design_variance: int = 5


def _load_strategy_config() -> dict[str, Any]:
    try:
        return json.loads(_STRATEGY_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"defaults": {"candidate_limit": 3}, "strategies": {}, "matches": []}


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _merge_template_maps(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base or {})
    for key, value in (override or {}).items():
        key_s = str(key or "").strip().lower()
        if not key_s:
            continue
        if isinstance(value, dict) and isinstance(out.get(key_s), dict):
            merged = dict(out.get(key_s) or {})
            merged.update(value)
            out[key_s] = merged
        else:
            out[key_s] = value
    return out


def load_brand_share_templates(
    *,
    brand_dir: str | Path | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    templates: dict[str, Any] = {}
    identity_data = identity if isinstance(identity, dict) else {}
    templates = _merge_template_maps(templates, identity_data.get("web_artifact_share_templates") or {})
    if brand_dir:
        root = Path(brand_dir).expanduser()
        templates = _merge_template_maps(
            templates,
            _read_json_file(root / "brand-identity.json").get("web_artifact_share_templates") or {},
        )
        templates = _merge_template_maps(
            templates,
            _read_json_file(root / "blackboard.json").get("web_artifact_share_templates") or {},
        )
    return templates


def resolve_share_template_preferences(
    entity_type: str,
    *,
    source_url: str = "",
    brand_dir: str | Path | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    templates = load_brand_share_templates(brand_dir=brand_dir, identity=identity)
    entity_key = str(entity_type or "").strip().lower()
    combined: dict[str, Any] = {}
    if isinstance(templates.get("default"), dict):
        combined.update(templates.get("default") or {})
    if entity_key and isinstance(templates.get(entity_key), dict):
        combined.update(templates.get(entity_key) or {})
    path = urlparse(str(source_url or "")).path.lower()
    route_key = ""
    if path.startswith("/u/"):
        route_key = "profile"
    elif path.startswith("/c/"):
        route_key = "community"
    elif path.startswith("/library/"):
        route_key = "library"
    elif path.startswith("/prompts/"):
        route_key = "prompt"
    elif path.startswith("/skills/"):
        route_key = "skill"
    if route_key and route_key != entity_key and isinstance(templates.get(route_key), dict):
        combined.update(templates.get(route_key) or {})
    preferred = combined.get("preferred_strategies") or []
    if isinstance(preferred, str):
        preferred = [preferred]
    combined["preferred_strategies"] = [
        str(item or "").strip()
        for item in preferred
        if str(item or "").strip()
    ]
    for key in (
        "selected_surface_strategy",
        "preferred_composition_mode",
        "detail_label",
        "cta",
    ):
        combined[key] = str(combined.get(key) or "").strip()
    return combined


def _matches_any(value: str, allowed: list[str] | None) -> bool:
    if not allowed:
        return True
    return value in {str(item or "").strip().lower() for item in allowed if str(item or "").strip()}


def _infer_source_shape(ctx: StrategyContext) -> str:
    product_truth = str(ctx.product_truth_expression or "").strip().lower()
    if ctx.entity_type in _GOVERNED_ENTITY_TYPES and ctx.source_url:
        return "governed_text"
    if any(token in product_truth for token in ("real prompt text", "real skill text", "real library text", "resolved from source", "resolved from ipfs")):
        return "source_resolved_text"
    if ctx.entity_type in {"proposal", "community", "dao"}:
        return "governance_record"
    if ctx.source_url:
        return "product_detail"
    return "generic"


def _needs_exact_text(ctx: StrategyContext, source_shape: str) -> bool:
    product_truth = str(ctx.product_truth_expression or "").strip().lower()
    if source_shape in {"governed_text", "source_resolved_text"}:
        return True
    return any(token in product_truth for token in ("real", "exact", "source-derived"))


def _rule_matches(ctx: StrategyContext, rule: dict[str, Any]) -> bool:
    when = rule.get("when") or {}
    return (
        _matches_any(ctx.render_backend, when.get("render_backends"))
        and _matches_any(ctx.material_type, when.get("material_types"))
        and _matches_any(ctx.entity_type, when.get("entity_types"))
    )


def _surface_keywords(text: str) -> set[str]:
    value = str(text or "").strip().lower()
    hits = set()
    for token in ("poster", "portrait", "story", "instagram", "feed", "square", "preview", "scan", "qr"):
        if token in value:
            hits.add(token)
    return hits


def _score_strategy(
    key: str,
    definition: dict[str, Any],
    *,
    ctx: StrategyContext,
    source_shape: str,
    exact_text_required: bool,
    seeded_rank: int,
    template_selected: str = "",
    template_preferred: list[str] | None = None,
) -> tuple[float, list[str]]:
    score = max(0.0, 12.0 - seeded_rank)
    reasons: list[str] = []

    if ctx.material_type in {str(item).strip().lower() for item in (definition.get("best_for_material_types") or []) if str(item).strip()}:
        score += 4.0
        reasons.append(f"fits {ctx.material_type} surface")
    if ctx.entity_type in {str(item).strip().lower() for item in (definition.get("best_for_entity_types") or []) if str(item).strip()}:
        score += 4.0
        reasons.append(f"fits {ctx.entity_type} artifact")
    if source_shape in {str(item).strip().lower() for item in (definition.get("preferred_source_shapes") or []) if str(item).strip()}:
        score += 3.0
        reasons.append(f"works for {source_shape.replace('_', ' ')}")
    if exact_text_required and definition.get("supports_exact_text"):
        score += 2.5
        reasons.append("preserves source-derived language")
    elif exact_text_required and not definition.get("supports_exact_text"):
        score -= 1.5

    surface_hits = _surface_keywords(ctx.target_surface or ctx.purpose)
    if key == "editorial_poster" and surface_hits & {"poster", "portrait", "story", "instagram"}:
        score += 2.0
        reasons.append("matches portrait/poster intent")
    if key == "compact_proof_card" and surface_hits & {"feed", "square", "preview"}:
        score += 2.0
        reasons.append("matches feed-speed scanning")
    if key == "qr_spotlight" and surface_hits & {"scan", "qr"}:
        score += 2.0
        reasons.append("scan-forward surface requested")
    if key == "capability_card" and ctx.entity_type == "skill":
        score += 3.0
        reasons.append("skill artifact benefits from capability framing")
    if key == "capability_card" and ctx.material_type == "social":
        score += 2.0
        reasons.append("square social suits capability framing")
    if key == "capability_card" and any(token in (ctx.purpose or "").lower() for token in ("capability", "workflow", "reusable")):
        score += 1.5
        reasons.append("purpose reads like capability promotion")
    if key == "collection_card" and ctx.entity_type == "library":
        score += 3.0
        reasons.append("library artifact benefits from collection framing")
    if key == "collection_card" and ctx.material_type == "x-feed":
        score += 2.0
        reasons.append("wide feed suits collection framing")
    if key in {"collection_card", "governance_snapshot"} and ctx.entity_type == "library":
        score += 1.5
        reasons.append("library context benefits from curation framing")
    if key == "governance_snapshot" and ctx.entity_type in {"proposal", "community", "dao"}:
        score += 3.0
        reasons.append("governance artifact benefits from status framing")

    low, high = definition.get("experimental_range") or [1, 10]
    try:
        low_i, high_i = int(low), int(high)
    except (TypeError, ValueError):
        low_i, high_i = 1, 10
    if low_i <= int(ctx.design_variance or 5) <= high_i:
        score += 1.0
        reasons.append("variance setting suits strategy")
    else:
        score -= 0.5

    if template_selected and key == template_selected:
        score += 8.0
        reasons.insert(0, "matches Sage session template")
    elif key in {str(item or "").strip() for item in (template_preferred or []) if str(item or "").strip()}:
        score += 4.0
        reasons.insert(0, "matches Sage session template family")

    return score, reasons


def recommend_surface_strategies(
    *,
    material_type: str,
    entity_type: str = "",
    render_backend: str = "native",
    source_url: str = "",
    purpose: str = "",
    target_surface: str = "",
    product_truth_expression: str = "",
    design_variance: int = 5,
    brand_dir: str | Path | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = StrategyContext(
        material_type=str(material_type or "").strip().lower(),
        entity_type=str(entity_type or "").strip().lower(),
        render_backend=("html" if str(render_backend or "").strip().lower() == "html" else "native"),
        source_url=str(source_url or "").strip(),
        purpose=str(purpose or "").strip(),
        target_surface=str(target_surface or "").strip(),
        product_truth_expression=str(product_truth_expression or "").strip(),
        design_variance=max(1, min(int(design_variance or 5), 10)),
    )
    source_shape = _infer_source_shape(ctx)
    exact_text_required = _needs_exact_text(ctx, source_shape)
    config = _load_strategy_config()
    definitions = config.get("strategies") or {}
    candidate_limit = max(1, int((config.get("defaults") or {}).get("candidate_limit") or 3))
    template = resolve_share_template_preferences(
        ctx.entity_type,
        source_url=ctx.source_url,
        brand_dir=brand_dir,
        identity=identity,
    )

    seeded_keys: list[str] = []
    for key in list(template.get("preferred_strategies") or []) + [template.get("selected_surface_strategy")]:
        strategy_key = str(key or "").strip()
        if strategy_key and strategy_key in definitions and strategy_key not in seeded_keys:
            seeded_keys.append(strategy_key)
    for rule in config.get("matches") or []:
        if _rule_matches(ctx, rule):
            for key in rule.get("strategies") or []:
                strategy_key = str(key or "").strip()
                if strategy_key and strategy_key not in seeded_keys and strategy_key in definitions:
                    seeded_keys.append(strategy_key)

    if not seeded_keys and ctx.render_backend == "html" and ctx.entity_type in _GOVERNED_ENTITY_TYPES:
        seeded_keys = ["compact_proof_card", "editorial_poster", "qr_spotlight"]

    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(seeded_keys):
        definition = definitions.get(key) or {}
        score, reasons = _score_strategy(
            key,
            definition,
            ctx=ctx,
            source_shape=source_shape,
            exact_text_required=exact_text_required,
            seeded_rank=index,
            template_selected=str(template.get("selected_surface_strategy") or ""),
            template_preferred=list(template.get("preferred_strategies") or []),
        )
        candidates.append(
            {
                "key": key,
                "label": str(definition.get("label") or key.replace("_", " ").title()),
                "summary": str(definition.get("summary") or ""),
                "layout_family": str(definition.get("layout_family") or ""),
                "prompt_directive": str(definition.get("prompt_directive") or ""),
                "score": round(score, 2),
                "evidence": reasons,
            }
        )

    candidates.sort(key=lambda item: (-float(item.get("score") or 0.0), item.get("key") or ""))
    candidates = candidates[:candidate_limit]
    selected = candidates[0] if candidates else {}

    selection_reason = ""
    if selected:
        evidence = list(selected.get("evidence") or [])
        reason_parts = evidence[:3] or ["best available fit for artifact, surface, and source shape"]
        selection_reason = "; ".join(reason_parts)

    return {
        "source_shape": source_shape,
        "exact_text_required": exact_text_required,
        "surface_strategy_candidates": candidates,
        "selected_surface_strategy": str(selected.get("key") or ""),
        "selected_surface_strategy_label": str(selected.get("label") or ""),
        "selected_surface_strategy_summary": str(selected.get("summary") or ""),
        "selected_surface_strategy_layout_family": str(selected.get("layout_family") or ""),
        "selected_surface_strategy_prompt_directive": str(selected.get("prompt_directive") or ""),
        "surface_strategy_reason": selection_reason,
    }


def load_surface_strategy_definition(key: str) -> dict[str, Any]:
    strategy_key = str(key or "").strip()
    if not strategy_key:
        return {}
    config = _load_strategy_config()
    definition = (config.get("strategies") or {}).get(strategy_key) or {}
    return {
        "key": strategy_key,
        "label": str(definition.get("label") or strategy_key.replace("_", " ").title()),
        "summary": str(definition.get("summary") or ""),
        "layout_family": str(definition.get("layout_family") or ""),
        "composition_modes": list(definition.get("composition_modes") or []),
        "asset_slots": list(definition.get("asset_slots") or []),
        "prompt_directive": str(definition.get("prompt_directive") or ""),
    }


def load_composition_profile(mode: str) -> dict[str, Any]:
    mode_key = str(mode or "").strip()
    if not mode_key:
        return {}
    config = _load_strategy_config()
    aliases = config.get("composition_profile_aliases") or {}
    resolved_key = str(aliases.get(mode_key) or mode_key)
    definition = (config.get("composition_profiles") or {}).get(resolved_key) or {}
    return {
        "key": resolved_key,
        "summary": str(definition.get("summary") or ""),
        "asset_slots": list(definition.get("asset_slots") or []),
        "reserved_zones": list(definition.get("reserved_zones") or []),
    }
