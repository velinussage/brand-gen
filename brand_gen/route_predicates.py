"""Scored predicate routing for brand-gen."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

try:
    from .pipeline_types import RoutingBrief
    from .material_planning import classify_workflow_route_smart
    from .request_intent import infer_illustration_only_request
    from .runtime_brand import load_workflow_router_rules
except ImportError:
    @dataclass
    class RoutingBrief:
        material_type: str | None = None
        material_key: str | None = None
        goal: str = ""
        request: str = ""
        render_backend: str = "native"
        source_url: str = ""
        entity_type: str = ""
        has_motion_reference: bool = False
        set_scope: bool = False
        reference_image_count: int = 0
        mode: str | None = None

    from material_planning import classify_workflow_route_smart  # type: ignore
    from request_intent import infer_illustration_only_request  # type: ignore
    from runtime_brand import load_workflow_router_rules  # type: ignore


_rules = load_workflow_router_rules()
_predicates = _rules.get("predicates", {})
PREDICATE_THRESHOLD = _predicates.get("threshold", 0.5)
MOTION_MATERIAL_KEYS = set(_predicates.get("motion_material_keys", ["landing_hero", "feature_animation"]))
TRANSLATE_MATERIAL_KEYS = set(_predicates.get("translate_material_keys", ["browser_illustration", "product_banner", "feature_illustration", "social"]))

# Tunable score values — loaded from data/workflow_router_rules.json
_scores = _predicates.get("scores", {})
_SCORE_SET_ORCHESTRATOR_MATCH = float(_scores.get("set_orchestrator_match", 1.0))
_SCORE_MOTION_REFERENCE_MATCH = float(_scores.get("motion_reference_match", 1.0))
_SCORE_MOTION_MATERIAL_MATCH = float(_scores.get("motion_material_match", 0.9))
_SCORE_TRANSLATE_MATERIAL_MATCH = float(_scores.get("translate_material_match", 0.9))
_SCORE_TRANSLATE_INSPIRATION_COMBO = float(_scores.get("translate_inspiration_combo", 0.7))
_SCORE_GENERATIVE_EXPLORE_BASELINE = float(_scores.get("generative_explore_baseline", 0.2))


def score_set_orchestrator(brief: RoutingBrief) -> float:
    return _SCORE_SET_ORCHESTRATOR_MATCH if brief.set_scope else 0.0


def score_motion_specialist(brief: RoutingBrief) -> float:
    if brief.has_motion_reference:
        return _SCORE_MOTION_REFERENCE_MATCH
    if brief.material_key in MOTION_MATERIAL_KEYS:
        return _SCORE_MOTION_MATERIAL_MATCH
    return 0.0


def score_reference_translate(brief: RoutingBrief) -> float:
    illustration_only = infer_illustration_only_request(goal=brief.goal, request=brief.request)
    if illustration_only and brief.material_key in TRANSLATE_MATERIAL_KEYS:
        return 0.0
    if str(brief.render_backend or "").strip().lower() == "html" and str(brief.source_url or "").strip():
        return _SCORE_TRANSLATE_MATERIAL_MATCH
    if str(brief.entity_type or "").strip().lower() in {"prompt", "skill", "library"} and str(brief.source_url or "").strip():
        return _SCORE_TRANSLATE_MATERIAL_MATCH
    if brief.material_key in TRANSLATE_MATERIAL_KEYS:
        return _SCORE_TRANSLATE_MATERIAL_MATCH
    if brief.reference_image_count > 0 and brief.mode == "inspiration":
        return _SCORE_TRANSLATE_INSPIRATION_COMBO
    return 0.0


def score_generative_explore(brief: RoutingBrief) -> float:
    if infer_illustration_only_request(goal=brief.goal, request=brief.request):
        return max(_SCORE_GENERATIVE_EXPLORE_BASELINE, 0.8)
    return _SCORE_GENERATIVE_EXPLORE_BASELINE


ROUTE_TABLE: list[tuple[str, Callable[[RoutingBrief], float]]] = [
    ("set_orchestrator", score_set_orchestrator),
    ("motion_specialist", score_motion_specialist),

    ("reference_translate", score_reference_translate),
    ("generative_explore", score_generative_explore),
]


def _build_default_route_result(key: str, *, score: float, method: str, score_vector: dict[str, float]) -> dict:
    routes = (load_workflow_router_rules().get("routes") or [])
    route = next((item for item in routes if item.get("key") == key), {}) or {
        "key": key,
        "label": key.replace("_", " "),
        "specialists": ["brand_director", "visual_composer", "critic_agent"],
        "required_assets": [],
        "next_commands": [],
        "notes": "",
    }
    return {
        "route_key": route.get("key") or key,
        "route": route,
        "material_key": key,
        "llm_routed": method == "llm",
        "score": score,
        "method": method,
        "score_vector": score_vector,
    }


def route_brief(brief: RoutingBrief) -> dict:
    scored = [(key, fn(brief), idx) for idx, (key, fn) in enumerate(ROUTE_TABLE)]
    scored.sort(key=lambda item: (-item[1], item[2]))
    best_key, best_score, _ = scored[0]
    score_vector = {key: round(fn(brief), 2) for key, fn in ROUTE_TABLE}
    print(f"route_scores: {score_vector}", file=sys.stderr)

    if best_score >= PREDICATE_THRESHOLD:
        return _build_default_route_result(best_key, score=best_score, method="predicate", score_vector=score_vector)

    try:
        result = classify_workflow_route_smart(
            brief.material_type,
            goal=brief.goal,
            request=brief.request,
            has_motion_reference=brief.has_motion_reference,
            set_scope=brief.set_scope,
        )
        if result:
            result.setdefault("score", best_score)
            result["method"] = "llm" if result.get("llm_routed") else "default"
            result["score_vector"] = score_vector
            return result
    except Exception as exc:
        print(f"route_classifier_warning: {exc}", file=sys.stderr)

    return _build_default_route_result("generative_explore", score=best_score, method="default", score_vector=score_vector)
