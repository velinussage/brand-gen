"""Framing-direction loader: stitch structured JSON + per-id prose markdown.

Each Sage framing direction has structured fields (id, label, keywords as
array or legacy space-separated string, source_priority, source_cues) and
three prose fields (directive, adoption_scene, style_anchor).

Per the architect's PR-2 split:
- Structured fields live in `data/sage_brand_contract.json::framing_directions[]`
  (or, after PR-4, `<brand>/contract.json::framing_directions[]`)
- Prose fields live in `<brand>/voice/framing/<id>.md` with frontmatter
  for `label` and one section per prose field

This module loads both, stitches them into the same `dict` shape the
existing `SAGE_FRAMING_DIRECTIONS` consumers expect, and falls back to
inline prose in the JSON when a markdown file is missing (transitional
support during migration).

Markdown file format:

    ---
    id: chosen-not-collected-sieve
    label: chosen-not-collected editorial sieve
    ---

    ## directive

    Frame Sage as selection rather than storage: a visible editorial sieve
    chooses one good capability and filters out harmful skill noise.

    ## adoption_scene

    an editorial selection sieve rejects noisy/generated skills and lets
    one curated capability become a runtime default

    ## style_anchor

    flat editorial sieve/gate composition with rejected noise outside the
    frame, one chosen capability artifact, restrained proof typography
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .frontmatter import parse_frontmatter


_PROSE_FIELDS = ("directive", "adoption_scene", "style_anchor")
_SECTION_RE = re.compile(r"^##\s+(directive|adoption_scene|style_anchor)\s*$", re.MULTILINE)


def voice_framing_dir(brand_dir: Path) -> Path:
    return Path(brand_dir).expanduser().resolve() / "voice" / "framing"


def parse_framing_markdown(text: str) -> dict[str, Any]:
    """Parse a single voice/framing/<id>.md into a {label, directive, adoption_scene, style_anchor} dict."""
    meta, body = parse_frontmatter(text)
    out: dict[str, Any] = {}
    if meta.get("label"):
        out["label"] = meta["label"]
    if meta.get("id"):
        out["id"] = meta["id"]
    sections: dict[str, str] = {}
    parts = _SECTION_RE.split(body)
    if len(parts) >= 3:
        i = 1
        while i + 1 < len(parts):
            name = parts[i].strip().lower()
            value = parts[i + 1].strip()
            if name in _PROSE_FIELDS:
                sections[name] = value
            i += 2
    out.update(sections)
    return out


def load_framing_markdown(brand_dir: Path, framing_id: str) -> dict[str, Any]:
    """Read voice/framing/<id>.md and return its parsed contents. Empty dict if missing."""
    path = voice_framing_dir(brand_dir) / f"{framing_id}.md"
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return parse_framing_markdown(text)


def write_framing_markdown(brand_dir: Path, *, framing_id: str, label: str, directive: str, adoption_scene: str, style_anchor: str) -> Path:
    """Write a voice/framing/<id>.md file. Returns the path."""
    framing_id = str(framing_id or "").strip()
    if not framing_id:
        raise ValueError("framing_id is required")
    voice_dir = voice_framing_dir(brand_dir)
    voice_dir.mkdir(parents=True, exist_ok=True)
    path = voice_dir / f"{framing_id}.md"
    parts = [
        "---",
        f"id: {framing_id}",
    ]
    if label:
        parts.append(f"label: {label}")
    parts.append("---")
    parts.append("")
    if directive:
        parts.append("## directive\n")
        parts.append(directive.strip() + "\n")
    if adoption_scene:
        parts.append("## adoption_scene\n")
        parts.append(adoption_scene.strip() + "\n")
    if style_anchor:
        parts.append("## style_anchor\n")
        parts.append(style_anchor.strip() + "\n")
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return path


def stitch_framing_direction(structured: dict[str, Any], brand_dir: Path | None) -> dict[str, Any]:
    """Stitch a structured JSON entry with markdown prose for the same id.

    Markdown wins for prose fields when present; falls back to JSON-inline prose;
    always returns a dict with the legacy shape.
    """
    framing_id = str(structured.get("id") or "").strip()
    out = dict(structured)
    if framing_id and brand_dir is not None:
        md = load_framing_markdown(brand_dir, framing_id)
        for key in _PROSE_FIELDS:
            value = str(md.get(key) or "").strip()
            if value:
                out[key] = value
        # md.label trumps json.label only if structured did not provide one
        if "label" not in out and md.get("label"):
            out["label"] = md["label"]
    return out


def load_framing_directions(structured_list: list[dict[str, Any]] | tuple[dict[str, Any], ...], brand_dir: Path | None) -> tuple[dict[str, Any], ...]:
    return tuple(stitch_framing_direction(item, brand_dir) for item in (structured_list or ()))
