"""Renders BRAND.md from canonical JSON state.

Single source of truth: JSON files in the brand workspace are canonical.
BRAND.md is a derived dossier rebuilt synchronously on every typed mutation.

Per Q14: render fires inside every typed verb (`update-palette`,
`append-forbidden-pattern`, etc.) so the dossier is always fresh; if render
breaks, mutations break (loud, not silent).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BRAND_MD_FILENAME = "BRAND.md"


@dataclass(frozen=True)
class BrandDossier:
    """Structured view of a brand's canonical state, ready to render."""

    name: str
    summary: str
    tone_words: list[str] = field(default_factory=list)
    palette: list[str] = field(default_factory=list)
    typography: dict[str, Any] = field(default_factory=dict)
    devices: list[str] = field(default_factory=list)
    forbidden_patterns: list[dict[str, str]] = field(default_factory=list)
    motion_grammar: dict[str, Any] = field(default_factory=dict)
    must_preserve: dict[str, Any] = field(default_factory=dict)
    do_not_collapse_into: list[str] = field(default_factory=list)
    voice_notes: list[str] = field(default_factory=list)
    scratchpad_sections: dict[str, list[str]] = field(default_factory=dict)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def build_dossier(brand_dir: Path) -> BrandDossier:
    """Reads canonical JSON state and assembles a typed dossier."""

    brand_dir = Path(brand_dir).expanduser().resolve()
    profile = _load_json(brand_dir / "brand-profile.json")
    identity = _load_json(brand_dir / "brand-identity.json")
    scratchpad = _load_json(brand_dir / "custom-scratchpad.json")

    identity_core = identity.get("identity_core") or {}
    must_preserve = identity_core.get("must_preserve") or {}

    palette: list[str] = []
    if isinstance(must_preserve.get("palette_direction"), list):
        palette = [str(c) for c in must_preserve["palette_direction"] if c]
    elif isinstance(profile.get("color_candidates"), list):
        palette = [str(c) for c in profile["color_candidates"] if c]

    typography_role = identity.get("typography") or {}

    sections: dict[str, list[str]] = {}
    if isinstance(scratchpad, dict):
        for section_name in ("global", "motion", "typography", "composition"):
            value = scratchpad.get(section_name)
            if isinstance(value, list):
                sections[section_name] = [str(item) for item in value if item]
            elif isinstance(value, dict):
                bullets = value.get("bullets")
                if isinstance(bullets, list):
                    sections[section_name] = [str(item) for item in bullets if item]

    forbidden_raw = scratchpad.get("forbidden_patterns") if isinstance(scratchpad, dict) else None
    forbidden: list[dict[str, str]] = []
    if isinstance(forbidden_raw, list):
        for item in forbidden_raw:
            if isinstance(item, dict):
                pattern = str(item.get("pattern") or "").strip()
                if pattern:
                    forbidden.append({
                        "pattern": pattern,
                        "reason": str(item.get("reason") or "").strip(),
                    })
            elif isinstance(item, str) and item.strip():
                forbidden.append({"pattern": item.strip(), "reason": ""})

    motion = scratchpad.get("motion_grammar") if isinstance(scratchpad, dict) else None
    if not isinstance(motion, dict):
        motion = {}

    devices_raw = identity_core.get("approved_primitives") or []
    devices = [str(d) for d in devices_raw if d]

    do_not_collapse = identity_core.get("do_not_collapse_into") or []
    if not isinstance(do_not_collapse, list):
        do_not_collapse = []

    voice_notes = identity.get("voice") or []
    if not isinstance(voice_notes, list):
        voice_notes = []

    return BrandDossier(
        name=str(profile.get("brand_name") or identity.get("brand", {}).get("name") or brand_dir.name),
        summary=str(profile.get("description") or identity.get("brand", {}).get("summary") or ""),
        tone_words=[str(t) for t in (profile.get("keywords") or identity_core.get("tone_words") or []) if t],
        palette=palette,
        typography=typography_role if isinstance(typography_role, dict) else {},
        devices=devices,
        forbidden_patterns=forbidden,
        motion_grammar=motion,
        must_preserve=must_preserve if isinstance(must_preserve, dict) else {},
        do_not_collapse_into=[str(item) for item in do_not_collapse if item],
        voice_notes=[str(v) for v in voice_notes if v],
        scratchpad_sections=sections,
    )


def _frontmatter(dossier: BrandDossier) -> str:
    lines = ["---", f"name: {dossier.name}"]
    if dossier.summary:
        summary = dossier.summary.replace("\n", " ").strip()
        lines.append(f"summary: {json.dumps(summary)}")
    if dossier.tone_words:
        lines.append(f"tone_words: {json.dumps(dossier.tone_words)}")
    if dossier.palette:
        lines.append(f"palette: {json.dumps(dossier.palette)}")
    if dossier.devices:
        lines.append(f"devices: {json.dumps(dossier.devices)}")
    if dossier.forbidden_patterns:
        pattern_names = [item["pattern"] for item in dossier.forbidden_patterns if item.get("pattern")]
        if pattern_names:
            lines.append(f"forbidden_patterns: {json.dumps(pattern_names)}")
    if dossier.motion_grammar:
        lines.append(f"motion: {json.dumps(dossier.motion_grammar)}")
    lines.append("schema: brand-md/v1")
    lines.append("---")
    return "\n".join(lines)


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items if item)


def _render_body(dossier: BrandDossier) -> str:
    parts: list[str] = []
    parts.append(f"# {dossier.name}")
    if dossier.summary:
        parts.append("")
        parts.append(dossier.summary)

    if dossier.tone_words:
        parts.extend(["", "## Tone", ", ".join(dossier.tone_words)])

    if dossier.palette:
        parts.extend(["", "## Palette"])
        for color in dossier.palette:
            parts.append(f"- `{color}`")

    if dossier.typography:
        parts.extend(["", "## Typography"])
        for role, value in sorted(dossier.typography.items()):
            parts.append(f"- **{role}**: `{value}`")

    if dossier.devices:
        parts.extend(["", "## Approved devices", _bullet_list(dossier.devices)])

    if dossier.motion_grammar:
        parts.extend(["", "## Motion grammar"])
        for key in ("director", "favored", "banned", "intensity"):
            if key in dossier.motion_grammar:
                value = dossier.motion_grammar[key]
                if isinstance(value, list):
                    if value:
                        parts.append(f"- **{key}**: {', '.join(str(v) for v in value)}")
                else:
                    parts.append(f"- **{key}**: {value}")

    if dossier.forbidden_patterns:
        parts.extend(["", "## Forbidden patterns"])
        for entry in dossier.forbidden_patterns:
            pattern = entry.get("pattern", "")
            reason = entry.get("reason", "")
            if reason:
                parts.append(f"- **{pattern}** — {reason}")
            else:
                parts.append(f"- **{pattern}**")

    if dossier.do_not_collapse_into:
        parts.extend(["", "## Do not collapse into", _bullet_list(dossier.do_not_collapse_into)])

    if dossier.voice_notes:
        parts.extend(["", "## Voice notes", _bullet_list(dossier.voice_notes)])

    for section_name, bullets in dossier.scratchpad_sections.items():
        if bullets:
            heading = section_name.capitalize()
            parts.extend(["", f"## {heading}", _bullet_list(bullets)])

    parts.append("")
    parts.append("---")
    parts.append("*BRAND.md is a rendered dossier. Edit JSON state through `bgen` verbs; this file is regenerated on every mutation.*")
    return "\n".join(parts)


def render_brand_md(brand_dir: Path) -> Path:
    """Renders BRAND.md from canonical JSON. Returns the written path.

    Safe to call from any typed mutation verb. Idempotent: identical canonical
    state produces identical BRAND.md.
    """

    brand_dir = Path(brand_dir).expanduser().resolve()
    dossier = build_dossier(brand_dir)
    out = brand_dir / BRAND_MD_FILENAME
    content = "\n\n".join([_frontmatter(dossier), _render_body(dossier)])
    out.write_text(content + "\n", encoding="utf-8")
    return out
