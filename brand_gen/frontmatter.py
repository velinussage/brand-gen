"""Read-only-after frontmatter convention for prose markdown files.

Files like `voice/*.md`, `brand-identity.md`, and `iteration-memory.md` may
ship with frontmatter declaring a read-only floor:

    ---
    read_only_after: 7c3a9f1
    read_only_reason: locked for hero-launch sequence
    ---

    # Title
    body...

If `read_only_after` is set to a git SHA, agents are warned (via the bgen
greeting and via `bgen contract status`) that further edits to that file
require human review. This is a *social* control — git is the actual
enforcement. Agents read this and either propose changes through PR
descriptions, or ask the human first.

The convention applies only to markdown files under `.brand-gen/brands/<brand>/`
and to repo-tracked prose files an agent might edit. Source code, JSON
state, and audit logs are out of scope (they have their own contracts).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML-ish frontmatter (key: value lines only) and return (meta, body).

    Returns (empty meta, original text) if no frontmatter is present.
    Intentionally narrow: we don't pull a YAML dependency for key:value pairs.
    """
    if not text:
        return {}, text
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    body = text[match.end():]
    return meta, body


def read_only_after(path: Path | str) -> dict[str, str]:
    """Return frontmatter dict if path has `read_only_after`; empty dict otherwise.

    Always-safe: if the path doesn't exist or isn't readable, returns empty.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    meta, _ = parse_frontmatter(text)
    if not meta.get("read_only_after"):
        return {}
    return meta


def is_read_only(path: Path | str) -> bool:
    return bool(read_only_after(path))


def read_only_warning(path: Path | str) -> str:
    """Human-readable warning string for a read-only-after file. Empty if not locked."""
    meta = read_only_after(path)
    if not meta:
        return ""
    sha = meta.get("read_only_after", "")
    reason = meta.get("read_only_reason", "")
    p = Path(path)
    parts = [f"⚠️  {p.name} is read-only-after {sha}."]
    if reason:
        parts.append(f"Reason: {reason}.")
    parts.append("Further edits require human review (see AGENTS.md).")
    return " ".join(parts)


def find_read_only_files(brand_dir: Path) -> list[dict[str, Any]]:
    """Walk a brand workspace and list all markdown files with read_only_after frontmatter.

    Returns a list of dicts with `path`, `read_only_after`, and `read_only_reason`.
    """
    out: list[dict[str, Any]] = []
    root = Path(brand_dir).expanduser().resolve()
    if not root.exists():
        return out
    for md_path in root.rglob("*.md"):
        meta = read_only_after(md_path)
        if not meta:
            continue
        out.append({
            "path": str(md_path),
            "read_only_after": meta.get("read_only_after", ""),
            "read_only_reason": meta.get("read_only_reason", ""),
        })
    return out
