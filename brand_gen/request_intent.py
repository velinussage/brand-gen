from __future__ import annotations

from typing import Iterable


ILLUSTRATION_ONLY_TERMS = [
    "illustration only",
    "just the illustration",
    "standalone illustration",
    "standalone artwork",
    "right-side illustration",
    "right side illustration",
    "right-side artwork",
    "right side artwork",
    "hero-side illustration",
    "hero side illustration",
    "not the full landing page",
    "not a full landing page",
    "not the page itself",
    "not the full page",
    "not a full page",
    "not a webpage",
    "not the full landing-page",
]

LANDING_PAGE_CONTEXT_TERMS = [
    "landing page illustration",
    "illustration for the landing page",
    "illustration that will go on the landing page",
    "landing-page illustration",
    "right side of the landing page",
    "right side of a landing page",
    "sit on the right side",
    "go on the landing page",
]

PAGE_CHROME_BAN_TERMS = [
    "no navigation",
    "no nav",
    "no headline block",
    "no left-copy column",
    "no left copy column",
    "no metrics band",
    "no full-page frame",
    "no full page frame",
    "no full-page layout",
    "no full page layout",
    "no browser mockup",
    "no page chrome",
]

INTERFACE_PAGE_ADJACENT_MATERIAL_KEYS = {
    "browser_illustration",
    "feature_illustration",
    "landing_hero",
    "product_banner",
    "terminal_hero",
    "command_illustration",
}

STRICT_PAGE_SCAFFOLD_MATERIAL_KEYS = {
    "browser_illustration",
    "landing_hero",
    "product_banner",
    "terminal_hero",
    "command_illustration",
}

STANDALONE_ILLUSTRATION_MATERIAL_KEYS = {
    "concept_illustration",
    "system_explainer_illustration",
    "editorial_metaphor_illustration",
    "brand_scene",
    "illustrated_brand_world",
}

SYSTEM_EXPLAINER_HINTS = {
    "system",
    "workflow",
    "how it works",
    "how-it-works",
    "explain",
    "explainer",
    "diagram",
    "protocol",
    "routing",
    "route",
    "flow",
    "mechanic",
    "mechanism",
    "causal",
    "legible",
    "docs",
}

EDITORIAL_METAPHOR_HINTS = {
    "metaphor",
    "editorial",
    "essay",
    "thought leadership",
    "thought-leadership",
    "narrative",
    "op-ed",
    "op ed",
    "manifesto",
    "story",
    "symbolic",
    "poetic",
}

PATTERN_BOARD_HINTS = {
    "pattern board",
    "exploration board",
    "explore",
    "exploration",
    "variants",
    "variant",
    "options",
    "review board",
    "presentation board",
    "moodboard",
    "mood board",
}


def _flatten_parts(parts: Iterable[object | None]) -> str:
    return " ".join(str(part or "").strip().lower() for part in parts if str(part or "").strip())


def illustration_only_hits(
    *,
    goal: str = "",
    request: str = "",
    purpose: str = "",
    target_surface: str = "",
    prompt_seed: str = "",
    briefing: str = "",
    preserve: list[str] | None = None,
    push: list[str] | None = None,
    ban: list[str] | None = None,
) -> list[str]:
    haystack = _flatten_parts([
        goal,
        request,
        purpose,
        target_surface,
        prompt_seed,
        briefing,
        " ".join(preserve or []),
        " ".join(push or []),
        " ".join(ban or []),
    ])
    hits: list[str] = []
    for term in ILLUSTRATION_ONLY_TERMS + LANDING_PAGE_CONTEXT_TERMS + PAGE_CHROME_BAN_TERMS:
        if term in haystack and term not in hits:
            hits.append(term)
    return hits


def infer_illustration_only_request(
    *,
    goal: str = "",
    request: str = "",
    purpose: str = "",
    target_surface: str = "",
    prompt_seed: str = "",
    briefing: str = "",
    preserve: list[str] | None = None,
    push: list[str] | None = None,
    ban: list[str] | None = None,
) -> bool:
    hits = illustration_only_hits(
        goal=goal,
        request=request,
        purpose=purpose,
        target_surface=target_surface,
        prompt_seed=prompt_seed,
        briefing=briefing,
        preserve=preserve,
        push=push,
        ban=ban,
    )
    if hits:
        return True
    haystack = _flatten_parts([goal, request, purpose, target_surface, prompt_seed, briefing])
    return (
        "landing page" in haystack
        and "illustration" in haystack
        and not any(term in haystack for term in ["full page", "landing hero", "browser mockup", "webpage"])
    )


def requires_standalone_illustration_material(material_key: str | None, *, illustration_only: bool = False) -> bool:
    key = str(material_key or "").strip().lower()
    return bool(illustration_only and key in STRICT_PAGE_SCAFFOLD_MATERIAL_KEYS)


def resolve_planner_material_type(
    material_type: str | None,
    *,
    purpose: str = "",
    target_surface: str = "",
    prompt_seed: str = "",
    briefing: str = "",
    product_truth_expression: str = "",
) -> tuple[str, str]:
    """Prefer the newer taxonomy when planning.

    Old material types still work for compatibility, but planners should bias
    toward the newer, narrower contracts that better match SaaS-useful output.
    Returns ``(resolved_material_type, note)``.
    """
    key = str(material_type or "").strip().lower()
    if not key:
        return key, ""
    haystack = _flatten_parts([
        purpose,
        target_surface,
        prompt_seed,
        briefing,
        product_truth_expression,
    ])

    if key == "brand-scene":
        return (
            "illustrated-brand-world",
            "Deprecated `brand-scene` request was upgraded to `illustrated-brand-world` so planning treats it as explicit worldbuilding instead of a generic scene.",
        )
    if key == "campaign-poster":
        return (
            "proof-poster",
            "Deprecated `campaign-poster` request was upgraded to `proof-poster` so the hierarchy is led by quote, screenshot, stat, or other proof payload rather than a dominant logo.",
        )
    if key == "bumper-animation":
        if any(term in haystack for term in ("landing", "hero", "homepage", "above the fold", "background", "website")):
            return (
                "landing-hero",
                "Deprecated `bumper-animation` request was upgraded to `landing-hero` because generic brand stings are no longer a default output; above-the-fold motion should be a purposeful 16:9 hero background/sidecar animation.",
            )
        return (
            "feature-animation",
            "Deprecated `bumper-animation` request was upgraded to `feature-animation` because generic brand stings are no longer a default output; motion should demonstrate one product capability or workflow.",
        )
    if key == "pattern-system":
        if any(term in haystack for term in PATTERN_BOARD_HINTS):
            return (
                "pattern-board",
                "Deprecated `pattern-system` request was upgraded to `pattern-board` because the brief sounds exploratory or board-oriented. Use `site-pattern-tile` for a single deployable site pattern.",
            )
        return (
            "site-pattern-tile",
            "Deprecated `pattern-system` request was upgraded to `site-pattern-tile` because production planning now defaults to one deployable site pattern instead of a board of variants.",
        )
    if key == "concept-illustration":
        editorial_hit = any(term in haystack for term in EDITORIAL_METAPHOR_HINTS)
        explainer_hit = any(term in haystack for term in SYSTEM_EXPLAINER_HINTS)
        if editorial_hit and not explainer_hit:
            return (
                "editorial-metaphor-illustration",
                "Deprecated `concept-illustration` request was upgraded to `editorial-metaphor-illustration` because the brief reads as essay-, story-, or metaphor-led rather than system-explainer-led.",
            )
        return (
            "system-explainer-illustration",
            "Deprecated `concept-illustration` request was upgraded to `system-explainer-illustration`; planners now default to the more SaaS-useful explainer contract unless the brief is explicitly metaphor-led.",
        )
    return key, ""
