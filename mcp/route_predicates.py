"""Scored predicate routing for brand-gen."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

try:
    from pipeline_types import RoutingBrief  # type: ignore
except Exception:
    @dataclass
    class RoutingBrief:
        material_type: str | None = None
        material_key: str | None = None
        goal: str = ""
        request: str = ""
        has_motion_reference: bool = False
        set_scope: bool = False
        reference_image_count: int = 0
        mode: str | None = None


PREDICATE_THRESHOLD = 0.5
MOTION_MATERIAL_KEYS = {"feature_animation", "brand_bumper"}

TRANSLATE_MATERIAL_KEYS = {"browser_illustration", "product_banner", "feature_illustration", "social"}


def score_set_orchestrator(brief: RoutingBrief) -> float:
    return 1.0 if brief.set_scope else 0.0


def score_motion_specialist(brief: RoutingBrief) -> float:
    if brief.has_motion_reference:
        return 1.0
    if brief.material_key in MOTION_MATERIAL_KEYS:
        return 0.9
    return 0.0



def score_reference_translate(brief: RoutingBrief) -> float:
    if brief.material_key in TRANSLATE_MATERIAL_KEYS:
        return 0.9
    if brief.reference_image_count > 0 and brief.mode == "inspiration":
        return 0.7
    return 0.0


def score_generative_explore(_brief: RoutingBrief) -> float:
    return 0.2


ROUTE_TABLE: list[tuple[str, Callable[[RoutingBrief], float]]] = [
    ("set_orchestrator", score_set_orchestrator),
    ("motion_specialist", score_motion_specialist),

    ("reference_translate", score_reference_translate),
    ("generative_explore", score_generative_explore),
]


def _build_default_route_result(key: str, *, score: float, method: str, score_vector: dict[str, float]) -> dict:
    from brand_iterate import load_workflow_router_rules

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
        from brand_iterate import classify_workflow_route_smart

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
    except Exception:
        pass

    return _build_default_route_result("generative_explore", score=best_score, method="default", score_vector=score_vector)
