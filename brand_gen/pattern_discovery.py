from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .blackboard import extract_feedback_patterns
from .runtime import INTERFACE_MATERIAL_KEYS, NON_INTERFACE_MATERIAL_KEYS, load_manifest, role_pack_material_key

_POSITIVE_TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "textless": ("textless", "no readable text", "render no text", "no text"),
    "single_thesis": ("one mechanism", "single", "one hero", "one library item", "one dominant"),
    "diagrammatic": ("diagram", "explainer", "flow", "provenance", "routed", "causal"),
    "editorial": ("editorial", "poster", "magazine", "print", "broadsheet"),
    "product_proof": ("proof", "product", "ui", "screenshot", "carrier"),
    "flat_graphic": ("flat", "graphic", "vector", "geometric", "crisp edges"),
    "photographic": ("photo", "photograph", "leica", "kodak", "portra", "50mm"),
    "quiet": ("quiet", "restraint", "calm", "negative space", "whitespace"),
}

_NEGATIVE_TAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "logo_dominance": ("logo too big", "oversized logo", "logo is too big", "giant logo", "logo monument"),
    "multi_lane": ("multiple parallel", "redundant", "too many", "competing", "different explanations"),
    "screenshot_drift": ("screenshot-like", "copied web app", "dashboard", "page recreation", "web-like"),
    "style_miss": ("wrong art style", "does not like the style", "not the right direction", "random editorial"),
    "text_garble": ("text is off", "gibberish text", "garbled", "readable text"),
}


def _normalize_material_key(material_type: str | None) -> str:
    return (role_pack_material_key(material_type) or "").strip()


def _material_group(material_type: str | None) -> str:
    key = _normalize_material_key(material_type)
    if key in INTERFACE_MATERIAL_KEYS:
        return "interface"
    if key in NON_INTERFACE_MATERIAL_KEYS:
        return "non_interface"
    return "general"


def _entry_text(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("raw_prompt") or ""),
        str(entry.get("notes") or ""),
        json.dumps(entry.get("critic_summary") or {}, ensure_ascii=False),
    ]
    return " ".join(part for part in parts if part).lower()


def _infer_score(entry: dict[str, Any]) -> float | None:
    score = entry.get("score")
    if isinstance(score, (int, float)):
        return float(score)
    notes = str(entry.get("notes") or "")
    hits = re.findall(r"(?<!\d)([0-5](?:\.\d+)?)\s*/\s*5", notes)
    if hits:
        try:
            return float(hits[-1])
        except ValueError:
            return None
    return None


def _infer_outcome(entry: dict[str, Any]) -> str:
    text = _entry_text(entry)
    score = _infer_score(entry)
    if "absolute reject" in text or "user rated 0/5" in text or "user override: 0/5" in text:
        return "negative"
    if score is not None and score <= 2:
        return "negative"
    if score is not None and score >= 4:
        return "positive"
    if "favorite" in text or "accepted" in text:
        return "positive"
    if (entry.get("critic_summary") or {}).get("p1"):
        return "negative"
    return "neutral"


def _detect_tags(text: str, patterns: dict[str, tuple[str, ...]]) -> list[str]:
    found: list[str] = []
    for tag, needles in patterns.items():
        if any(needle in text for needle in needles):
            found.append(tag)
    return found


def _candidate_from_entry(version_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    text = _entry_text(entry)
    feedback = extract_feedback_patterns(
        {
            "notes": entry.get("notes") or "",
            "score": _infer_score(entry),
            "status": "rejected" if _infer_outcome(entry) == "negative" else "",
            "critique": {
                "approved": not bool((entry.get("critic_summary") or {}).get("p1")),
                "p1": list((entry.get("critic_summary") or {}).get("p1") or []),
                "p2": list((entry.get("critic_summary") or {}).get("p2") or []),
                "clean": list((entry.get("critic_summary") or {}).get("clean") or []),
                "refinement_suggestion": "",
            },
        }
    )
    prompt = str(entry.get("raw_prompt") or "").strip()
    first_sentence = re.split(r"(?<=[.!?])\s+", prompt)[0].strip() if prompt else ""
    return {
        "version": version_id,
        "material_type": entry.get("material_type") or "",
        "model": entry.get("model") or "",
        "score": _infer_score(entry),
        "outcome": _infer_outcome(entry),
        "prompt": prompt,
        "prompt_excerpt": first_sentence[:180],
        "positive_tags": _detect_tags(text, _POSITIVE_TAG_PATTERNS),
        "negative_tags": _detect_tags(text, _NEGATIVE_TAG_PATTERNS),
        "signals": feedback,
    }


def _dedupe_keep_order(items: list[str], limit: int = 6) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = str(item).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(str(item).strip())
        if len(out) >= limit:
            break
    return out


def discover_prompt_patterns(
    brand_dir: Path | None,
    material_type: str | None,
    *,
    limit: int = 3,
) -> dict[str, Any]:
    if not brand_dir:
        return {
            "retrieval_mode": "none",
            "hypotheses": [],
            "recommended_moves": [],
            "avoid_moves": [],
            "packet": "",
        }

    manifest = load_manifest(brand_dir)
    versions = dict((manifest.get("versions") or {}))
    target_material = str(material_type or "").strip().lower()
    target_group = _material_group(material_type)

    exact_candidates: list[dict[str, Any]] = []
    group_candidates: list[dict[str, Any]] = []
    for version_id, entry in versions.items():
        if not isinstance(entry, dict):
            continue
        entry_material = str(entry.get("material_type") or "").strip().lower()
        if not entry_material:
            continue
        candidate = _candidate_from_entry(version_id, entry)
        if entry_material == target_material:
            exact_candidates.append(candidate)
        elif _material_group(entry_material) == target_group:
            group_candidates.append(candidate)

    retrieval_mode = "material_exact" if exact_candidates else ("material_group_fallback" if group_candidates else "none")
    pool = exact_candidates or group_candidates
    positive_pool = [item for item in pool if item["outcome"] == "positive"]
    negative_pool = [item for item in pool if item["outcome"] == "negative"]

    if not positive_pool:
        # Fall back to the best neutral examples so the system still has a
        # few hypotheses to vary around instead of a single canonical memory.
        positive_pool = sorted(
            [item for item in pool if item["outcome"] == "neutral"],
            key=lambda item: (item.get("score") or 0, item.get("version") or ""),
            reverse=True,
        )[:limit]

    positive_pool = sorted(
        positive_pool,
        key=lambda item: ((item.get("score") or 0), len(item.get("positive_tags") or []), item.get("version") or ""),
        reverse=True,
    )

    hypotheses: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, ...]] = set()
    for item in positive_pool:
        signature = tuple(sorted(item.get("positive_tags") or [])) or (item.get("model") or "",)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        prefer = _dedupe_keep_order(
            list(item.get("signals", {}).get("prefer") or []) + list(item.get("positive_tags") or []),
            limit=4,
        )
        hypotheses.append(
            {
                "version": item.get("version") or "",
                "model": item.get("model") or "",
                "score": item.get("score"),
                "borrow": prefer,
                "excerpt": item.get("prompt_excerpt") or "",
            }
        )
        if len(hypotheses) >= limit:
            break

    recommended_counter = Counter()
    for item in positive_pool:
        for tag in item.get("positive_tags") or []:
            recommended_counter[tag] += 1
        for signal in item.get("signals", {}).get("prefer") or []:
            recommended_counter[signal] += 1

    avoid_counter = Counter()
    for item in negative_pool:
        for tag in item.get("negative_tags") or []:
            avoid_counter[tag] += 1
        for signal in item.get("signals", {}).get("avoid") or []:
            avoid_counter[signal] += 1
        for signal in item.get("signals", {}).get("failure_patterns") or []:
            avoid_counter[signal] += 1

    recommended_moves = [item for item, _ in recommended_counter.most_common(6)]
    avoid_moves = [item for item, _ in avoid_counter.most_common(6)]

    packet_lines: list[str] = []
    if hypotheses:
        packet_lines.append("Pattern hypotheses:")
        for hypothesis in hypotheses:
            borrow = ", ".join(hypothesis.get("borrow") or []) or "reuse the strongest composition logic"
            version = hypothesis.get("version") or "prior"
            model = hypothesis.get("model") or "unknown-model"
            packet_lines.append(f"- {version} ({model}): bias toward {borrow}")
    if avoid_moves:
        packet_lines.append("Avoid repeated failure patterns: " + "; ".join(avoid_moves[:4]))

    return {
        "retrieval_mode": retrieval_mode,
        "hypotheses": hypotheses,
        "recommended_moves": recommended_moves,
        "avoid_moves": avoid_moves,
        "packet": "\n".join(packet_lines).strip(),
    }
