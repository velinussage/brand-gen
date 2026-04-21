from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

from .custom_scratchpad import custom_scratchpad_json_path, custom_scratchpad_md_path, load_custom_scratchpad_json


MOTION_GRAMMAR_HEADING = "Motion grammar"


def render_motion_grammar_markdown(
    *,
    director: str,
    favored: list[str] | None = None,
    banned: list[str] | None = None,
    intensity: str = "",
) -> str:
    favored = [str(item).strip() for item in (favored or []) if str(item).strip()]
    banned = [str(item).strip() for item in (banned or []) if str(item).strip()]
    lines = [f"## {MOTION_GRAMMAR_HEADING}", ""]
    if director.strip():
        lines.append(f"- Director token: {director.strip()}")
    if intensity.strip():
        lines.append(f"- Intensity: {intensity.strip()}")
    if favored:
        lines.append(f"- Favored moves: {'; '.join(favored)}")
    if banned:
        lines.append(f"- Banned moves: {'; '.join(banned)}")
    lines.append("")
    return "\n".join(lines)


def replace_motion_grammar_section(brand_dir: Path, markdown_section: str) -> Path:
    path = custom_scratchpad_md_path(brand_dir)
    text = path.read_text() if path.exists() else "# Custom scratchpad\n"
    pattern = re.compile(rf"(?ms)^## {re.escape(MOTION_GRAMMAR_HEADING)}\s*\n.*?(?=^## |\Z)")
    section = markdown_section.strip() + "\n"
    if pattern.search(text):
        updated = pattern.sub(section, text).rstrip() + "\n"
    else:
        updated = text.rstrip() + "\n\n" + section
    path.write_text(updated)
    return path


def set_motion_grammar(
    brand_dir: Path,
    *,
    director: str,
    favored: list[str] | None = None,
    banned: list[str] | None = None,
    intensity: str = "",
    via_cli: bool = False,
) -> dict:
    if not via_cli:
        warnings.warn(
            "set_motion_grammar() direct helper calls are deprecated; use the typed CLI/MCP tool instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    payload = {
        "director": str(director or "").strip(),
        "favored": [str(item).strip() for item in (favored or []) if str(item).strip()],
        "banned": [str(item).strip() for item in (banned or []) if str(item).strip()],
        "intensity": str(intensity or "").strip(),
    }
    data = load_custom_scratchpad_json(brand_dir)
    data["motion_grammar"] = payload
    custom_scratchpad_json_path(brand_dir).write_text(json.dumps(data, indent=2) + "\n")
    replace_motion_grammar_section(
        brand_dir,
        render_motion_grammar_markdown(
            director=payload["director"],
            favored=payload["favored"],
            banned=payload["banned"],
            intensity=payload["intensity"],
        ),
    )
    return payload
