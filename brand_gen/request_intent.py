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
    "brand_scene",
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
