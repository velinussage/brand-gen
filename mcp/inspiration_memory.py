"""Inspiration-memory persistence and consolidation.

This module intentionally stores inspiration synthesis outside ``brand-identity.json``.
Brand identity is a curated, versioned artifact; inspiration memory is volatile workspace
state derived from the current inspiration image set. Keep the two lifecycles separate.

Execution model:
- standalone command / optional post-step (`consolidate-inspiration`)
- one remote VLM JSON analysis per image when a provider key is available
- local aggregation / ranking / persistence after the per-image analyses return
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

from .runtime_brand import load_system_prompt
from .runtime_io import load_json_file
from .runtime_models import SUPPORTED_IMAGE_EXTS
from .runtime_support import dedupe_keep_order
from .vlm_critique import run_vlm_json

INSPIRATION_MEMORY_SYSTEM = load_system_prompt("inspiration_analysis")

DEFAULT_INSPIRATION_MEMORY = {
    "schema_version": 1,
    "created_at": "",
    "updated_at": "",
    "storage_scope": "brand_materials_state",
    "execution_mode": "standalone_command",
    "analysis_strategy": "per_image_remote_vlm_then_local_reduce",
    "providers_used": [],
    "sources": [],
    "summary": "",
    "palette_direction": [],
    "typography_cues": [],
    "composition_archetypes": [],
    "surface_finishes": [],
    "motion_cues": [],
    "negative_cues": [],
    "seed_prompt": "",
    "confidence_notes": "",
    "analyses": [],
}


def inspiration_memory_paths(brand_dir: Path) -> tuple[Path, Path]:
    return brand_dir / "inspiration-memory.json", brand_dir / "inspiration-memory.md"


def normalize_inspiration_memory(payload: dict | None) -> dict:
    out = dict(DEFAULT_INSPIRATION_MEMORY)
    if isinstance(payload, dict):
        out.update(payload)
    for key in (
        "providers_used",
        "sources",
        "palette_direction",
        "typography_cues",
        "composition_archetypes",
        "surface_finishes",
        "motion_cues",
        "negative_cues",
        "analyses",
    ):
        out[key] = list(out.get(key) or [])
    return out


def load_inspiration_memory(brand_dir: Path) -> dict:
    json_path, _ = inspiration_memory_paths(brand_dir)
    if not json_path.exists():
        return dict(DEFAULT_INSPIRATION_MEMORY)
    return normalize_inspiration_memory(load_json_file(json_path))


def render_inspiration_memory_markdown(payload: dict) -> str:
    payload = normalize_inspiration_memory(payload)
    lines = ["# Inspiration memory", ""]
    if payload.get("summary"):
        lines += ["## Summary", payload["summary"], ""]
    for heading, key in (
        ("Palette direction", "palette_direction"),
        ("Typography cues", "typography_cues"),
        ("Composition archetypes", "composition_archetypes"),
        ("Surface finishes", "surface_finishes"),
        ("Motion cues", "motion_cues"),
        ("Negative cues", "negative_cues"),
    ):
        items = payload.get(key) or []
        if items:
            lines += [f"## {heading}"] + [f"- {item}" for item in items] + [""]
    if payload.get("seed_prompt"):
        lines += ["## Seed prompt", payload["seed_prompt"], ""]
    if payload.get("confidence_notes"):
        lines += ["## Confidence notes", payload["confidence_notes"], ""]
    if payload.get("sources"):
        lines += ["## Sources"]
        for item in payload["sources"]:
            source = item.get("path") or item.get("source") or ""
            note = item.get("confidence_notes") or ""
            lines.append(f"- {source}{': ' + note if note else ''}")
        lines.append("")
    if payload.get("providers_used"):
        lines += ["## Execution", f"- Providers used: {', '.join(payload['providers_used'])}", ""]
    return "\n".join(lines).rstrip() + "\n"


def save_inspiration_memory(brand_dir: Path, payload: dict) -> tuple[Path, Path]:
    json_path, md_path = inspiration_memory_paths(brand_dir)
    normalized = normalize_inspiration_memory(payload)
    json_path.write_text(json.dumps(normalized, indent=2) + "\n")
    md_path.write_text(render_inspiration_memory_markdown(normalized))
    return json_path, md_path


def resolve_inspiration_images(brand_dir: Path, images: list[str] | None = None) -> list[Path]:
    if images:
        candidates = [Path(item).expanduser().resolve() for item in images if str(item).strip()]
    else:
        inspiration_dir = brand_dir / "inspiration"
        candidates = sorted(path.resolve() for path in inspiration_dir.glob("*")) if inspiration_dir.exists() else []
    return [path for path in candidates if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTS]


def _normalize_hexes(items: list[str]) -> list[str]:
    values: list[str] = []
    for item in items:
        values.extend(match.upper() for match in re.findall(r"#[0-9A-Fa-f]{6}", str(item or "")))
    return dedupe_keep_order(values)


def _normalize_terms(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        value = re.sub(r"\s+", " ", str(item or "").strip())
        if value:
            cleaned.append(value)
    return dedupe_keep_order(cleaned)


def _parse_analysis(parsed: dict | None, image_path: Path) -> dict:
    parsed = parsed if isinstance(parsed, dict) else {}
    return {
        "path": str(image_path),
        "summary": str(parsed.get("summary") or "").strip(),
        "palette_hexes": _normalize_hexes(list(parsed.get("palette_hexes") or [])),
        "typography_cues": _normalize_terms(list(parsed.get("typography_cues") or []))[:4],
        "composition_archetypes": _normalize_terms(list(parsed.get("composition_archetypes") or []))[:4],
        "surface_finishes": _normalize_terms(list(parsed.get("surface_finishes") or []))[:4],
        "motion_cues": _normalize_terms(list(parsed.get("motion_cues") or []))[:4],
        "negative_cues": _normalize_terms(list(parsed.get("negative_cues") or []))[:4],
        "confidence_notes": str(parsed.get("confidence_notes") or "").strip(),
        "vlm_available": bool(parsed),
        "vlm_provider": str(parsed.get("vlm_provider") or "") if parsed else "",
    }


def analyze_inspiration_image(image_path: Path, *, env: dict | None = None) -> dict:
    prompt = (
        "Analyze the attached inspiration image for transferable brand direction. "
        "Extract palette, typography cues, composition patterns, surface finishes, motion attitude, and anti-patterns. "
        "Return JSON only."
    )
    return _parse_analysis(run_vlm_json(image_path, INSPIRATION_MEMORY_SYSTEM, prompt, env=env, max_tokens=700), image_path)


def _rank_terms(analyses: list[dict], key: str, *, limit: int = 8) -> list[str]:
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    labels: dict[str, str] = {}
    for idx, analysis in enumerate(analyses):
        for raw in analysis.get(key) or []:
            value = re.sub(r"\s+", " ", str(raw or "").strip())
            if not value:
                continue
            normalized = value.lower()
            counts[normalized] += 1
            first_seen.setdefault(normalized, idx)
            labels.setdefault(normalized, value)
    ranked = sorted(counts, key=lambda item: (-counts[item], first_seen[item], item))
    return [labels[item] for item in ranked[:limit]]


def build_inspiration_seed_prompt(payload: dict) -> str:
    parts: list[str] = []
    compositions = list(payload.get("composition_archetypes") or [])
    typography = list(payload.get("typography_cues") or [])
    finishes = list(payload.get("surface_finishes") or [])
    motion = list(payload.get("motion_cues") or [])
    negative = list(payload.get("negative_cues") or [])
    if compositions:
        parts.append(f"Favor {', '.join(compositions[:2])}.")
    if typography:
        parts.append(f"Typography cues: {', '.join(typography[:2])}.")
    if finishes:
        parts.append(f"Surface feel: {', '.join(finishes[:2])}.")
    if motion:
        parts.append(f"Motion attitude: {', '.join(motion[:2])}.")
    if negative:
        parts.append(f"Avoid literal borrowing such as {', '.join(negative[:2])}.")
    return " ".join(parts).strip()


def consolidate_inspiration_memory(brand_dir: Path, *, images: list[str] | None = None, env: dict | None = None) -> dict:
    image_paths = resolve_inspiration_images(brand_dir, images)
    if not image_paths:
        raise SystemExit(f"No inspiration images found. Add files under {brand_dir / 'inspiration'} or pass --image.")

    analyses = [analyze_inspiration_image(path, env=env) for path in image_paths]
    if not any(item.get("vlm_available") for item in analyses):
        raise SystemExit("No VLM provider available for inspiration consolidation. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

    payload = normalize_inspiration_memory(
        {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "storage_scope": "brand_materials_state",
            "execution_mode": "standalone_command",
            "analysis_strategy": "per_image_remote_vlm_then_local_reduce",
            "providers_used": dedupe_keep_order([str(item.get("vlm_provider") or "").strip() for item in analyses if str(item.get("vlm_provider") or "").strip()]),
            "sources": [
                {
                    "path": item["path"],
                    "vlm_provider": item.get("vlm_provider") or "",
                    "confidence_notes": item.get("confidence_notes") or "",
                }
                for item in analyses
            ],
            "summary": " ".join(
                part
                for part in [
                    f"Recurring composition cues: {', '.join(_rank_terms(analyses, 'composition_archetypes', limit=2))}."
                    if _rank_terms(analyses, "composition_archetypes", limit=2)
                    else "",
                    f"Typography cues lean toward {', '.join(_rank_terms(analyses, 'typography_cues', limit=2))}."
                    if _rank_terms(analyses, "typography_cues", limit=2)
                    else "",
                    f"Surface finish tends toward {', '.join(_rank_terms(analyses, 'surface_finishes', limit=2))}."
                    if _rank_terms(analyses, "surface_finishes", limit=2)
                    else "",
                ]
                if part
            ).strip(),
            "palette_direction": _normalize_hexes([item for analysis in analyses for item in (analysis.get("palette_hexes") or [])])[:8],
            "typography_cues": _rank_terms(analyses, "typography_cues", limit=6),
            "composition_archetypes": _rank_terms(analyses, "composition_archetypes", limit=6),
            "surface_finishes": _rank_terms(analyses, "surface_finishes", limit=6),
            "motion_cues": _rank_terms(analyses, "motion_cues", limit=6),
            "negative_cues": _rank_terms(analyses, "negative_cues", limit=6),
            "confidence_notes": f"Summarized from {len(image_paths)} inspiration images; VLM coverage on {sum(1 for item in analyses if item.get('vlm_available'))}/{len(analyses)} images.",
            "analyses": analyses,
        }
    )
    payload["seed_prompt"] = build_inspiration_seed_prompt(payload)
    return payload
