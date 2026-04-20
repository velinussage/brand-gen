"""Custom scratchpad — agent-editable per-brand persistent state.

Two files live next to iteration-memory.json and learnings.json:

- `custom-scratchpad.md`  — free-form markdown written by brand-philosopher,
  brand-critic, and the user. Style directives, motion grammar, director
  tokens, whatever the brand has converged on. Injected into the prompt
  prelude verbatim (capped like other non-interface snippets) next to the
  iteration-memory and blackboard-learning snippets.

- `custom-scratchpad.json` — machine-read structured sidecar:
    {
      "model_overrides_by_material": {"<material>": {"model": "...", "mode": "..."}},
      "forbidden_patterns": [
        {"pattern": "purple gradients", "reason": "slop tell", "source_version": "v032"}
      ]
    }

Writes are direct — agents have write permission and the existing philosopher
pattern already edits files like design-philosophy.md directly. No two-lane
gating. The json sidecar is append-only via `append_forbidden_pattern` from
the critic.
"""
from __future__ import annotations

import json
from pathlib import Path

from .runtime_io import load_json_file

DEFAULT_CUSTOM_SCRATCHPAD_JSON = {
    "schema_type": "custom_scratchpad",
    "schema_version": 1,
    "model_overrides_by_material": {},
    "forbidden_patterns": [],
}


def custom_scratchpad_md_path(brand_dir: Path) -> Path:
    return brand_dir / "custom-scratchpad.md"


def custom_scratchpad_json_path(brand_dir: Path) -> Path:
    return brand_dir / "custom-scratchpad.json"


def load_custom_scratchpad_markdown(brand_dir: Path) -> str:
    path = custom_scratchpad_md_path(brand_dir)
    if not path.exists():
        return ""
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def load_custom_scratchpad_json(brand_dir: Path) -> dict:
    path = custom_scratchpad_json_path(brand_dir)
    if not path.exists():
        return dict(DEFAULT_CUSTOM_SCRATCHPAD_JSON)
    data = load_json_file(path) or {}
    merged = dict(DEFAULT_CUSTOM_SCRATCHPAD_JSON)
    merged.update(data)
    merged["model_overrides_by_material"] = dict(merged.get("model_overrides_by_material") or {})
    merged["forbidden_patterns"] = list(merged.get("forbidden_patterns") or [])
    return merged


def build_custom_scratchpad_snippet(brand_dir: Path, material_type: str | None) -> str:
    """Assemble the prompt-prelude snippet. Prefers the markdown narrative,
    falls back to structured bans if no markdown exists."""
    md = load_custom_scratchpad_markdown(brand_dir)
    data = load_custom_scratchpad_json(brand_dir)
    forbidden = [
        str(item.get("pattern") or "").strip()
        for item in data.get("forbidden_patterns") or []
        if str(item.get("pattern") or "").strip()
    ]
    parts: list[str] = []
    if md:
        parts.append("Custom scratchpad:")
        parts.append(md)
    if forbidden:
        parts.append("Forbidden patterns (hard bans):")
        for pattern in forbidden[:8]:
            parts.append(f"- {pattern}")
    return "\n".join(parts).strip()


def resolve_model_override(brand_dir: Path, material_type: str | None) -> dict:
    """Return {model, mode} for this material, or {} if none configured."""
    if not material_type:
        return {}
    data = load_custom_scratchpad_json(brand_dir)
    raw = (data.get("model_overrides_by_material") or {}).get(material_type) or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    model = str(raw.get("model") or "").strip()
    mode = str(raw.get("mode") or "").strip()
    if model:
        out["model"] = model
    if mode:
        out["mode"] = mode
    return out


def append_forbidden_pattern(
    brand_dir: Path,
    *,
    pattern: str,
    reason: str = "",
    source_version: str = "",
) -> None:
    pattern = str(pattern or "").strip()
    if not pattern:
        return
    data = load_custom_scratchpad_json(brand_dir)
    existing = data.get("forbidden_patterns") or []
    lowered = {str(item.get("pattern") or "").strip().lower() for item in existing}
    if pattern.lower() in lowered:
        return
    existing.append(
        {
            "pattern": pattern,
            "reason": str(reason or "").strip(),
            "source_version": str(source_version or "").strip(),
        }
    )
    data["forbidden_patterns"] = existing[-50:]
    custom_scratchpad_json_path(brand_dir).write_text(json.dumps(data, indent=2) + "\n")
