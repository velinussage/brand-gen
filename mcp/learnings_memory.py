from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

from .runtime_io import load_json_file

DEFAULT_LEARNINGS_MEMORY = {
    "version": 1,
    "brand": "",
    "modelPreferences": [],
    "colorInsights": [],
    "compositionPatterns": [],
    "failurePatterns": [],
    "messagingInsights": [],
    "audienceInsights": [],
    "lastUpdated": "",
}

PROMOTION_THRESHOLDS = {
    "failurePatterns": 2,
    "compositionPatterns": 2,
    "modelPreferences": 2,
}


def learnings_memory_path(brand_dir: Path) -> Path:
    return brand_dir / "learnings.json"


def _now_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _learning_text(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        return str(entry.get("text") or "").strip()
    return ""


def normalize_learnings_memory(payload: dict | None) -> dict:
    out = dict(DEFAULT_LEARNINGS_MEMORY)
    if isinstance(payload, dict):
        out.update(payload)
    for key in [
        "modelPreferences",
        "colorInsights",
        "compositionPatterns",
        "failurePatterns",
        "messagingInsights",
        "audienceInsights",
    ]:
        out[key] = list(out.get(key) or [])
    return out


def load_learnings_memory(brand_dir: Path) -> dict:
    path = learnings_memory_path(brand_dir)
    if not path.exists():
        return dict(DEFAULT_LEARNINGS_MEMORY)
    return normalize_learnings_memory(load_json_file(path))


def save_learnings_memory(brand_dir: Path, payload: dict) -> Path:
    path = learnings_memory_path(brand_dir)
    normalized = normalize_learnings_memory(payload)
    path.write_text(json.dumps(normalized, indent=2) + "\n")
    return path


def _dedupe_learning_entries(items: list[object]) -> list[object]:
    seen: set[str] = set()
    out: list[object] = []
    for item in items:
        text = _learning_text(item).lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(item)
    return out


def _append_learning_entry(memory: dict, bucket: str, entry: dict) -> bool:
    items = list(memory.get(bucket) or [])
    existing = {_learning_text(item).lower(): item for item in items if _learning_text(item)}
    key = _learning_text(entry).lower()
    if not key:
        return False
    if key in existing:
        return False
    items.append(entry)
    memory[bucket] = _dedupe_learning_entries(items)
    return True


def summarize_learnings_memory(payload: dict, *, limit: int = 5) -> dict:
    normalized = normalize_learnings_memory(payload)
    buckets = {}
    for key in [
        "modelPreferences",
        "colorInsights",
        "compositionPatterns",
        "failurePatterns",
        "messagingInsights",
        "audienceInsights",
    ]:
        items = list(normalized.get(key) or [])
        preview: list[dict] = []
        for item in items[-limit:]:
            if isinstance(item, dict):
                preview.append(
                    {
                        "text": str(item.get("text") or ""),
                        "material_type": str(item.get("material_type") or ""),
                        "promoted_at": str(item.get("promoted_at") or ""),
                        "evidence_versions": list(item.get("evidence_versions") or []),
                    }
                )
            else:
                preview.append(
                    {
                        "text": str(item),
                        "material_type": "",
                        "promoted_at": "",
                        "evidence_versions": [],
                    }
                )
        buckets[key] = preview
    return {
        "lastUpdated": str(normalized.get("lastUpdated") or ""),
        "counts": {key: len(normalized.get(key) or []) for key in buckets},
        "recent": buckets,
    }


def promote_blackboard_lessons_to_learnings(
    brand_dir: Path,
    *,
    board: dict | None = None,
    material_type: str | None = None,
) -> dict:
    from .blackboard import _is_negative_feedback, _is_positive_feedback
    from .runtime_models import role_pack_material_key

    if board is None:
        from .blackboard import load_blackboard

        board = load_blackboard(brand_dir)
    memory = load_learnings_memory(brand_dir)
    timestamp = _now_timestamp()
    promoted: list[dict] = []
    requested_key = role_pack_material_key(material_type) if material_type else None
    rollups = dict((board or {}).get("feedback_rollups") or {})

    for material_key, rollup in rollups.items():
        if requested_key and material_key != requested_key:
            continue
        feedback_items = list((rollup or {}).get("recent_feedback") or [])
        failure_counter: Counter[str] = Counter()
        failure_versions: dict[str, list[str]] = {}
        success_counter: Counter[str] = Counter()
        success_versions: dict[str, list[str]] = {}
        recipe_counter: Counter[str] = Counter()
        recipe_versions: dict[str, list[str]] = {}

        for item in feedback_items:
            version = str(item.get("version") or "").strip()
            signals = item.get("signals") or {}
            if _is_negative_feedback(item):
                for text in signals.get("failure_patterns") or []:
                    failure_counter[text] += 1
                    failure_versions.setdefault(text, [])
                    if version and version not in failure_versions[text]:
                        failure_versions[text].append(version)
            if _is_positive_feedback(item):
                for text in signals.get("success_patterns") or signals.get("prefer") or []:
                    success_counter[text] += 1
                    success_versions.setdefault(text, [])
                    if version and version not in success_versions[text]:
                        success_versions[text].append(version)
                label = " + ".join(
                    part
                    for part in [
                        str(item.get("mode") or "").strip(),
                        str(item.get("model") or "").strip(),
                        "with refs" if item.get("has_reference_images") else "without refs",
                    ]
                    if part
                )
                if label:
                    recipe_counter[label] += 1
                    recipe_versions.setdefault(label, [])
                    if version and version not in recipe_versions[label]:
                        recipe_versions[label].append(version)

        for text, count in failure_counter.items():
            if count < PROMOTION_THRESHOLDS["failurePatterns"]:
                continue
            entry = {
                "text": f"[{material_key}] Avoid: {text}",
                "material_type": material_key,
                "evidence_versions": failure_versions.get(text, [])[:6],
                "source": "blackboard_promotion",
                "promoted_at": timestamp,
            }
            if _append_learning_entry(memory, "failurePatterns", entry):
                promoted.append({"bucket": "failurePatterns", **entry})

        for text, count in success_counter.items():
            if count < PROMOTION_THRESHOLDS["compositionPatterns"]:
                continue
            entry = {
                "text": f"[{material_key}] Prefer: {text}",
                "material_type": material_key,
                "evidence_versions": success_versions.get(text, [])[:6],
                "source": "blackboard_promotion",
                "promoted_at": timestamp,
            }
            if _append_learning_entry(memory, "compositionPatterns", entry):
                promoted.append({"bucket": "compositionPatterns", **entry})

        for text, count in recipe_counter.items():
            if count < PROMOTION_THRESHOLDS["modelPreferences"]:
                continue
            entry = {
                "text": f"[{material_key}] Winning setup: {text}",
                "material_type": material_key,
                "evidence_versions": recipe_versions.get(text, [])[:6],
                "source": "blackboard_promotion",
                "promoted_at": timestamp,
            }
            if _append_learning_entry(memory, "modelPreferences", entry):
                promoted.append({"bucket": "modelPreferences", **entry})

    if promoted:
        memory["lastUpdated"] = timestamp
        path = save_learnings_memory(brand_dir, memory)
    else:
        path = learnings_memory_path(brand_dir)
    return {
        "path": str(path),
        "memory": memory,
        "promoted": promoted,
    }


__all__ = [
    "DEFAULT_LEARNINGS_MEMORY",
    "PROMOTION_THRESHOLDS",
    "learnings_memory_path",
    "load_learnings_memory",
    "normalize_learnings_memory",
    "promote_blackboard_lessons_to_learnings",
    "save_learnings_memory",
    "summarize_learnings_memory",
]
