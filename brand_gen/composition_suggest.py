"""Composition vocabulary lookup and layout suggestions.

Pure data-driven layout suggestions from data/composition_vocabulary.json.
No ML, no VLM — just structured lookups with novelty filtering.

Key functions:
    load_composition_vocabulary  — load and cache the vocabulary JSON
    suggest_layouts              — return layout suggestions for a material type
    suggest_layouts_for_plan     — higher-level wrapper reading from a plan dict
    format_layout_suggestions    — human-readable numbered list for agent display
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .runtime_paths import REPO_ROOT
from .runtime_models import role_pack_material_key

__all__ = [
    "load_composition_vocabulary",
    "suggest_layouts",
    "suggest_layouts_for_plan",
    "format_layout_suggestions",
]

COMPOSITION_VOCABULARY_PATH = REPO_ROOT / "data" / "composition_vocabulary.json"

_vocabulary_cache: dict | None = None


def load_composition_vocabulary() -> dict:
    """Load and cache the composition vocabulary JSON."""
    global _vocabulary_cache
    if _vocabulary_cache is not None:
        return _vocabulary_cache
    if not COMPOSITION_VOCABULARY_PATH.exists():
        return {}
    try:
        data = json.loads(COMPOSITION_VOCABULARY_PATH.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    _vocabulary_cache = data
    return _vocabulary_cache


def suggest_layouts(
    material_type: str,
    *,
    count: int = 4,
    exclude: list[str] | None = None,
) -> list[dict]:
    """Return *count* layout suggestions for *material_type*.

    Each suggestion dict contains:
        name, label, description, composition, prompt_fragment, tags

    *exclude* is a list of layout ``name`` values to skip (for novelty —
    the caller passes names of recently-used layouts).
    """
    vocab = load_composition_vocabulary()
    layouts_by_key: dict[str, list[dict]] = vocab.get("layouts") or {}
    default_layout: dict = vocab.get("default_layout") or {}

    key = role_pack_material_key(material_type)
    candidates: list[dict] = layouts_by_key.get(key or "") or []

    # Fall back: try the raw hyphenated key in case the vocab uses it directly
    if not candidates and material_type:
        alt_key = material_type.strip().lower().replace("-", "_")
        candidates = layouts_by_key.get(alt_key) or []

    exclude_set = set(exclude or [])
    filtered = [c for c in candidates if c.get("name") not in exclude_set]

    # If exclusion removed everything, fall back to unfiltered
    if not filtered and candidates:
        filtered = list(candidates)

    # Shuffle for variety, then truncate
    shuffled = list(filtered)
    random.shuffle(shuffled)
    selected = shuffled[:count]

    results: list[dict] = []
    for item in selected:
        results.append({
            "name": item.get("name", ""),
            "label": item.get("label", ""),
            "description": item.get("description", ""),
            "composition": item.get("composition", ""),
            "prompt_fragment": item.get("prompt_fragment", ""),
            "tags": list(item.get("tags") or []),
        })

    # If we have fewer than requested and a default exists, pad with it
    if len(results) < count and default_layout:
        results.append({
            "name": default_layout.get("name", "default"),
            "label": "Default Layout",
            "description": "A versatile centered editorial layout that adapts to any material type.",
            "composition": default_layout.get("composition", ""),
            "prompt_fragment": default_layout.get("composition", ""),
            "tags": ["default", "centered", "editorial"],
        })

    return results


def suggest_layouts_for_plan(
    plan: dict,
    *,
    recent_versions: list[dict] | None = None,
    count: int = 4,
) -> list[dict]:
    """Higher-level wrapper that reads material_type from a plan dict.

    Checks *recent_versions* (e.g. from ``bgen show``) to find recently-used
    composition families and excludes them for diversity.  Returns suggestions
    sorted by relevance (tag overlap with plan context).
    """
    material_type = plan.get("material_type") or ""
    if not material_type:
        return []

    # Derive exclude list from recent versions
    exclude: list[str] = []
    for ver in (recent_versions or []):
        layout_name = (ver.get("layout") or ver.get("composition_layout") or "").strip()
        if layout_name and layout_name not in exclude:
            exclude.append(layout_name)

    suggestions = suggest_layouts(material_type, count=count, exclude=exclude)

    # Sort by relevance: count tag overlap with plan-level signals
    plan_tags: set[str] = set()
    for field in ("tags", "preserve", "push"):
        for val in (plan.get(field) or []):
            plan_tags.add(str(val).strip().lower())
    if plan.get("system_mechanic"):
        plan_tags.add(str(plan["system_mechanic"]).strip().lower())

    def _relevance(item: dict) -> int:
        item_tags = {str(t).strip().lower() for t in (item.get("tags") or [])}
        return len(item_tags & plan_tags)

    suggestions.sort(key=_relevance, reverse=True)
    return suggestions


def format_layout_suggestions(suggestions: list[dict]) -> str:
    """Format suggestions as a human-readable numbered list.

    Each entry shows the label, a one-sentence description, and the
    ``prompt_fragment`` as a ready-to-copy value.
    """
    if not suggestions:
        return "No layout suggestions available for this material type."

    lines: list[str] = []
    for idx, item in enumerate(suggestions, 1):
        label = item.get("label") or item.get("name") or f"Layout {idx}"
        desc = item.get("description") or ""
        fragment = item.get("prompt_fragment") or ""
        tags = ", ".join(item.get("tags") or [])

        lines.append(f"{idx}. {label}")
        if desc:
            lines.append(f"   {desc}")
        if tags:
            lines.append(f"   Tags: {tags}")
        if fragment:
            lines.append(f"   Prompt fragment:")
            lines.append(f"   {fragment}")
        lines.append("")

    return "\n".join(lines).rstrip()
