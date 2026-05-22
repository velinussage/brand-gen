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
      "html_share_card_policy": {
        "status": "retired_except_proof_poster",
        "allowed_material_types": ["proof-poster"],
        "reason": "..."
      },
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
import re
import warnings
from pathlib import Path

from .runtime_io import load_json_file

DEFAULT_CUSTOM_SCRATCHPAD_JSON = {
    "schema_type": "custom_scratchpad",
    "schema_version": 1,
    "model_overrides_by_material": {},
    "forbidden_patterns": [],
    "html_share_card_policy": {},
    "motion_grammar": {},
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


def _coerce_list(value: object) -> list[object]:
    if isinstance(value, list):
        return list(value)
    return []


def _coerce_dict(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _normalize_forbidden_patterns(items: list[object]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            pattern = str(item.get("pattern") or "").strip()
            reason = str(item.get("reason") or "").strip()
            source_version = str(item.get("source_version") or "").strip()
        else:
            pattern = str(item or "").strip()
            reason = ""
            source_version = ""
        if not pattern:
            continue
        key = pattern.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "pattern": pattern,
                "reason": reason,
                "source_version": source_version,
            }
        )
    return out


def load_custom_scratchpad_json(brand_dir: Path) -> dict:
    path = custom_scratchpad_json_path(brand_dir)
    if not path.exists():
        return dict(DEFAULT_CUSTOM_SCRATCHPAD_JSON)
    data = load_json_file(path) or {}
    merged = dict(DEFAULT_CUSTOM_SCRATCHPAD_JSON)
    merged.update(data)
    merged["model_overrides_by_material"] = _coerce_dict(merged.get("model_overrides_by_material"))
    merged["forbidden_patterns"] = _normalize_forbidden_patterns(_coerce_list(merged.get("forbidden_patterns")))
    merged["html_share_card_policy"] = _coerce_dict(merged.get("html_share_card_policy"))
    merged["motion_grammar"] = _coerce_dict(merged.get("motion_grammar"))
    return merged


def html_share_card_block_reason(brand_dir: Path, material_type: str | None) -> str:
    """Return a brand-specific block reason for HTML/share-card generation.

    The HTML renderer is intentionally available for many brands, but some
    brand workspaces retire it after learning that deterministic share-card
    chrome is harming the brand.  Keep that choice in the brand scratchpad
    instead of hard-coding it into the global renderer.
    """
    data = load_custom_scratchpad_json(brand_dir)
    policy = data.get("html_share_card_policy") if isinstance(data.get("html_share_card_policy"), dict) else {}
    status = str(policy.get("status") or "").strip().lower().replace("-", "_")
    if not status:
        # Back-compat for pre-policy Sage scratchpads: the markdown carried the
        # retired-flow rule before the JSON field existed.
        md = load_custom_scratchpad_markdown(brand_dir).lower()
        if "retire the artifact/share-card flow" in md or "avoid `--render-backend html`" in md:
            status = "retired_except_proof_poster"
            policy = {
                "allowed_material_types": ["proof-poster"],
                "reason": "Brand scratchpad retires the artifact/share-card flow; only explicit proof-poster proof work may use the deterministic HTML renderer.",
            }
    if status not in {"retired", "retired_except_proof_poster", "disabled", "block"}:
        return ""

    material = str(material_type or "").strip().lower()
    allowed = [
        str(item or "").strip().lower()
        for item in (policy.get("allowed_material_types") or [])
        if str(item or "").strip()
    ]
    if status == "retired_except_proof_poster" and not allowed:
        allowed = ["proof-poster"]
    if material and material in allowed:
        return ""

    reason = str(policy.get("reason") or "").strip()
    if not reason:
        reason = "Brand scratchpad retires the artifact/share-card flow for this material."
    return reason


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
        brand_key = str(brand_dir.name or "").strip().lower()
        sage_context = brand_key == "sage" or "sage" in md.lower()
        conditional_terms = ("robot", "humanoid", "agent-workshop", "central hub", "switchboard")
        hard_patterns: list[str] = []
        default_suppressions: list[str] = []
        for pattern in forbidden[:8]:
            if sage_context and any(term in pattern.lower() for term in conditional_terms):
                default_suppressions.append(pattern)
            else:
                hard_patterns.append(pattern)
        if hard_patterns:
            parts.append("Forbidden patterns (hard bans):")
            for pattern in hard_patterns:
                parts.append(f"- {pattern}")
        if default_suppressions:
            parts.append("Default suppressions (allowed only when the user specifically asks for this framing):")
            for pattern in default_suppressions:
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


SECTION_HEADINGS = {
    "global": "Global bans",
    "motion": "Motion bans",
    "typography": "Typography bans",
    "composition": "Composition bans",
}


def append_scratchpad_note(
    brand_dir: Path,
    *,
    section: str,
    bullet: str,
    via_cli: bool = False,
) -> int:
    if not via_cli:
        warnings.warn(
            "append_scratchpad_note() direct helper calls are deprecated; use the typed CLI/MCP tool instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    heading = SECTION_HEADINGS.get(str(section or "").strip().lower())
    if not heading:
        raise ValueError(f"unknown scratchpad section: {section!r}")
    bullet = str(bullet or "").strip().lstrip("- ").strip()
    if not bullet:
        return 0
    path = custom_scratchpad_md_path(brand_dir)
    text = path.read_text() if path.exists() else "# Custom scratchpad\n"
    bullet_line = f"- {bullet}"
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)")
    match = pattern.search(text)
    if not match:
        block = f"\n\n## {heading}\n\n{bullet_line}\n"
        path.write_text(text.rstrip() + block)
        return len(block)
    body = match.group(1)
    existing_lines = {line.strip() for line in body.splitlines() if line.strip()}
    if bullet_line in existing_lines:
        return 0
    insertion = match.end(1)
    updated = text[:insertion] + ("" if body.endswith("\n") or not body else "\n") + bullet_line + "\n" + text[insertion:]
    path.write_text(updated)
    return len(bullet_line) + 1


def append_forbidden_pattern(
    brand_dir: Path,
    *,
    pattern: str,
    reason: str = "",
    source_version: str = "",
    via_cli: bool = False,
) -> None:
    if not via_cli:
        warnings.warn(
            "append_forbidden_pattern() direct helper calls are deprecated; use the typed CLI/MCP tool instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    pattern = str(pattern or "").strip()
    if not pattern:
        return
    data = load_custom_scratchpad_json(brand_dir)
    existing = _normalize_forbidden_patterns(_coerce_list(data.get("forbidden_patterns")))
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
