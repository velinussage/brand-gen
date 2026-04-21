from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .runtime import load_iteration_memory
from .runtime_models import role_pack_material_key
from .runtime_support import dedupe_keep_order

_KEYWORD_CAPABILITIES: list[tuple[tuple[str, ...], str, str]] = [
    (("publish", "author"), "skill publishing", "authoring"),
    (("skill", "skills"), "reusable skills", "skills"),
    (("prompt", "prompts"), "prompt curation", "content"),
    (("behavior", "behaviors"), "behaviors and prompt packs", "content"),
    (("library", "libraries"), "library discovery", "distribution"),
    (("discover", "discovery", "search"), "discovery and browsing", "discovery"),
    (("review", "reviewed"), "review and provenance", "trust"),
    (("govern", "governance"), "community governance", "governance"),
    (("approve", "approval", "promotion"), "approvals and promotion", "governance"),
    (("provenance", "trust"), "trust and provenance", "trust"),
    (("distribute", "distribution"), "trusted distribution", "distribution"),
    (("cli",), "CLI workflows", "runtime"),
    (("mcp",), "MCP tools", "runtime"),
    (("agent", "agents"), "agent orchestration", "agents"),
    (("repo", "canon", "shipped"), "repo canon and shipped truth", "source_of_truth"),
]

_LINEAR_STORY_MARKERS = (
    "publish",
    "govern",
    "approve",
    "distribute",
    "->",
    "→",
)


def _collect_brand_text(identity: dict[str, Any]) -> list[str]:
    messaging = identity.get("messaging") or {}
    parts = [
        str(((identity.get("brand") or {}).get("summary") or "")),
        str(messaging.get("elevator") or ""),
        " ".join(str(item) for item in (messaging.get("approved_claims") or [])),
        " ".join(str(item) for item in (messaging.get("value_propositions") or [])),
        " ".join(str(item) for item in (identity.get("material_dna") or {}).values()),
    ]
    return [part for part in parts if part.strip()]


def derive_brand_capability_candidates(identity: dict[str, Any]) -> list[dict[str, str]]:
    haystack = " ".join(_collect_brand_text(identity)).lower()
    candidates: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for keywords, label, category in _KEYWORD_CAPABILITIES:
        if not any(keyword in haystack for keyword in keywords):
            continue
        if label in seen_labels:
            continue
        seen_labels.add(label)
        candidates.append({"label": label, "category": category})
    return candidates


def _recent_negative_text(brand_dir: Path, material_type: str | None) -> str:
    memory = load_iteration_memory(brand_dir)
    negatives = list(memory.get("negative_examples") or [])
    material_key = role_pack_material_key(material_type)
    parts: list[str] = []
    for item in reversed(negatives):
        if material_key and role_pack_material_key(item.get("material_type")) != material_key:
            continue
        text = str(item.get("summary") or "").strip()
        if text:
            parts.append(text.lower())
        if len(parts) >= 4:
            break
    return " ".join(parts)


def build_capability_focus_context(
    *,
    brand_dir: Path,
    identity: dict[str, Any],
    material_type: str | None,
    product_truth_expression: str = "",
    artifact_scope: str = "",
) -> dict[str, Any]:
    candidates = derive_brand_capability_candidates(identity)
    if not candidates:
        return {
            "candidates": [],
            "selected": [],
            "directive": "",
            "avoid_repeating_linear_story": False,
        }

    negative_text = _recent_negative_text(brand_dir, material_type)
    current_story = str(product_truth_expression or "").lower()
    current_linear = all(marker in current_story for marker in ("publish", "govern", "distribute")) or any(marker in current_story for marker in ("->", "→"))
    repeated_story_signal = current_linear and any(term in negative_text for term in ["same", "repeat", "flow", "diagram", "infographic"]) or (artifact_scope == "illustration_only" and current_linear)

    selected: list[dict[str, str]] = []
    used_categories: set[str] = set()
    ordered_candidates = list(candidates)
    if repeated_story_signal:
        preferred_categories = ["runtime", "agents", "skills", "content", "discovery", "trust", "governance", "distribution"]
        ordered_candidates = sorted(
            candidates,
            key=lambda item: (
                preferred_categories.index(item["category"]) if item["category"] in preferred_categories else len(preferred_categories),
                candidates.index(item),
            ),
        )
    for item in ordered_candidates:
        if repeated_story_signal and item["label"] in {"community governance", "approvals and promotion", "trusted distribution"}:
            continue
        if item["category"] in used_categories:
            continue
        used_categories.add(item["category"])
        selected.append(item)
        if len(selected) >= 4:
            break
    if len(selected) < 3:
        for item in candidates:
            if item in selected:
                continue
            selected.append(item)
            if len(selected) >= 4:
                break

    labels = [item["label"] for item in selected]
    directive = ""
    if labels:
        directive = (
            "Show a broader capability family rooted in this brand, not one repeated linear flow. "
            f"Prioritize distinct capability moments such as {', '.join(labels[:4])}."
        )
    return {
        "candidates": candidates,
        "selected": selected,
        "directive": directive,
        "avoid_repeating_linear_story": bool(repeated_story_signal),
    }
