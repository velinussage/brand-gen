from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .runtime_io import load_json_file

DEFAULT_ITERATION_MEMORY = {
    "version": 1,
    "brand_notes": [],
    "positive_examples": [],
    "negative_examples": [],
    "copy_notes": [],
    "messaging_notes": [],
    "material_notes": {},
}

def iteration_memory_paths(brand_dir: Path) -> tuple[Path, Path]:
    return brand_dir / "iteration-memory.json", brand_dir / "iteration-memory.md"


def normalize_iteration_memory(payload: dict | None) -> dict:
    out = dict(DEFAULT_ITERATION_MEMORY)
    if isinstance(payload, dict):
        out.update(payload)
    out["brand_notes"] = list(out.get("brand_notes") or [])
    out["positive_examples"] = list(out.get("positive_examples") or [])
    out["negative_examples"] = list(out.get("negative_examples") or [])
    out["copy_notes"] = list(out.get("copy_notes") or [])
    out["messaging_notes"] = list(out.get("messaging_notes") or [])
    out["material_notes"] = dict(out.get("material_notes") or {})
    return out


def load_iteration_memory(brand_dir: Path) -> dict:
    json_path, _ = iteration_memory_paths(brand_dir)
    if not json_path.exists():
        return dict(DEFAULT_ITERATION_MEMORY)
    return normalize_iteration_memory(load_json_file(json_path))


def render_iteration_memory_markdown(payload: dict) -> str:
    lines = ["# Iteration memory", ""]
    if payload.get("brand_notes"):
        lines += ["## Brand notes"] + [f"- {item}" for item in payload["brand_notes"]] + [""]
    if payload.get("messaging_notes"):
        lines += ["## Messaging notes"] + [f"- {item}" for item in payload["messaging_notes"]] + [""]
    if payload.get("copy_notes"):
        lines += ["## Copy notes"] + [f"- {item}" for item in payload["copy_notes"]] + [""]
    if payload.get("negative_examples"):
        lines += ["## Negative examples"]
        for item in payload["negative_examples"][-12:]:
            lines.append(f"- {item.get('version','note')}: {item.get('material_type','')} — {item.get('summary','')}")
        lines.append("")
    if payload.get("positive_examples"):
        lines += ["## Positive examples"]
        for item in payload["positive_examples"][-12:]:
            lines.append(f"- {item.get('version','note')}: {item.get('material_type','')} — {item.get('summary','')}")
        lines.append("")
    material_notes = payload.get("material_notes") or {}
    if material_notes:
        lines += ["## Material-specific notes"]
        for key, items in material_notes.items():
            lines.append(f"### {key}")
            for item in items[-8:]:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_iteration_memory(brand_dir: Path, payload: dict) -> tuple[Path, Path]:
    json_path, md_path = iteration_memory_paths(brand_dir)
    normalized = normalize_iteration_memory(payload)
    json_path.write_text(json.dumps(normalized, indent=2) + "\n")
    md_path.write_text(render_iteration_memory_markdown(normalized))
    return json_path, md_path


def add_iteration_note(memory: dict, note: str, *, material_type: str | None = None, bucket: str = "brand_notes", role_pack_material_key_fn: Callable[[str | None], str | None] | None = None) -> dict:
    if not note.strip():
        return memory
    memory = normalize_iteration_memory(memory)
    if bucket == "material":
        key = (role_pack_material_key_fn(material_type) if role_pack_material_key_fn else None) or (material_type or "general")
        memory["material_notes"].setdefault(key, [])
        if note not in memory["material_notes"][key]:
            memory["material_notes"][key].append(note)
        return memory
    if note not in memory.get(bucket, []):
        memory[bucket].append(note)
    return memory


def capture_feedback_into_iteration_memory(
    memory: dict,
    version: str,
    entry: dict,
    notes: str | None,
    score: int | None,
    status: str | None,
    *,
    role_pack_material_key_fn: Callable[[str | None], str | None] | None = None,
) -> dict:
    memory = normalize_iteration_memory(memory)
    if role_pack_material_key_fn is None:
        from .runtime_models import role_pack_material_key

        role_pack_material_key_fn = role_pack_material_key
    material_type = entry.get("material_type") or ""
    summary = (notes or "").strip() or "Feedback recorded."
    record = {
        "version": version,
        "material_type": material_type,
        "summary": summary,
        "score": score,
        "status": status or "",
    }
    target_bucket = None
    if status == "favorite" or (score is not None and score >= 4):
        target_bucket = "positive_examples"
    elif status == "rejected" or (score is not None and score <= 2):
        target_bucket = "negative_examples"
    if target_bucket:
        existing = memory.get(target_bucket, [])
        existing = [item for item in existing if item.get("version") != version]
        existing.append(record)
        memory[target_bucket] = existing[-20:]
    if notes and notes.strip():
        memory = add_iteration_note(
            memory,
            notes.strip(),
            material_type=material_type,
            bucket="material",
            role_pack_material_key_fn=role_pack_material_key_fn,
        )
    return memory


def build_iteration_memory_snippet(
    brand_dir: Path,
    material_type: str | None,
    *,
    role_pack_material_key_fn: Callable[[str | None], str | None] | None = None,
    interface_material_keys: set[str] | None = None,
) -> str:
    if role_pack_material_key_fn is None or interface_material_keys is None:
        from .runtime_models import INTERFACE_MATERIAL_KEYS, role_pack_material_key

        role_pack_material_key_fn = role_pack_material_key_fn or role_pack_material_key
        interface_material_keys = interface_material_keys or INTERFACE_MATERIAL_KEYS
    memory = load_iteration_memory(brand_dir)
    lines: list[str] = []
    key = role_pack_material_key_fn(material_type) or (material_type or "")
    brand_notes = memory.get("brand_notes") or []
    messaging_notes = memory.get("messaging_notes") or []
    copy_notes = memory.get("copy_notes") or []
    material_notes = (memory.get("material_notes") or {}).get(key, [])
    negative = memory.get("negative_examples") or []
    if brand_notes:
        lines.append("Recent brand memory:")
        for item in brand_notes[-2:]:
            lines.append(f"- {item}")
    if messaging_notes and (key in interface_material_keys or key in {"social", "campaign_poster", "merch_poster", "landing_hero", "podcast_cover", "podcast_banner", "content_card", "editorial_card", "data_card", "quote_card", "announcement_card", "process_card"}):
        lines.append("Recent messaging notes:")
        for item in messaging_notes[-3:]:
            lines.append(f"- {item}")
    if material_notes:
        lines.append("Recent material-specific notes:")
        for item in material_notes[-3:]:
            lines.append(f"- {item}")
    if copy_notes and (key in interface_material_keys or key in {"social", "campaign_poster", "merch_poster", "podcast_cover", "podcast_banner", "content_card", "editorial_card", "data_card", "quote_card", "announcement_card", "process_card"}):
        lines.append("Recent copy notes:")
        for item in copy_notes[-2:]:
            lines.append(f"- {item}")
    if negative:
        recent_negative = [item for item in reversed(negative) if not key or role_pack_material_key_fn(item.get("material_type")) == key]
        if recent_negative:
            lines.append("Recent misses to avoid:")
            for item in recent_negative[:2]:
                lines.append(f"- {item.get('summary')}")
    return "\n".join(lines).strip()
