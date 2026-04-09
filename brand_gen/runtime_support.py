from __future__ import annotations

import html
import re
from typing import Iterable


def version_sort_key(version_id: str) -> int:
    match = re.match(r"v(\d+)", str(version_id or "").strip())
    return int(match.group(1)) if match else 0


def html_escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def dedupe_keep_order(items: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


__all__ = ["dedupe_keep_order", "html_escape", "version_sort_key"]
