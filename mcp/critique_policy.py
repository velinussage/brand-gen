from __future__ import annotations

import time
from typing import Any


def _clean_blocking(blocking: list[str] | tuple[str, ...] | None) -> list[str]:
    items: list[str] = []
    for item in blocking or []:
        value = str(item or "").strip()
        if value:
            items.append(value)
    return items


def build_critique_policy(
    *,
    critique_mode: str,
    entrypoint: str,
    blocking: list[str] | tuple[str, ...] | None = None,
    allow_blocking: bool = False,
    bypass_reason: str | None = None,
) -> dict[str, Any]:
    normalized_mode = "advisory" if str(critique_mode or "").strip().lower() == "advisory" else "strict"
    blocking_items = _clean_blocking(blocking)
    has_blocking = bool(blocking_items)

    bypass_requested = bool(allow_blocking and has_blocking and normalized_mode == "strict")
    bypass_recorded = bypass_requested
    blocks_generation = bool(normalized_mode == "strict" and has_blocking and not bypass_recorded)
    blocking_policy = (
        "report_only"
        if normalized_mode == "advisory"
        else ("allow_with_recorded_bypass" if bypass_recorded else "block_generation")
    )

    return {
        "critique_mode": normalized_mode,
        "blocking_policy": blocking_policy,
        "entrypoint": str(entrypoint or ""),
        "has_blocking_issues": has_blocking,
        "blocks_generation": blocks_generation,
        "bypass_requested": bypass_requested,
        "bypass_recorded": bypass_recorded,
        "bypass_reason": str(bypass_reason or "") if bypass_recorded else "",
        "bypass_recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S") if bypass_recorded else "",
    }


def normalize_critique_policy(
    raw: dict[str, Any] | None,
    *,
    default_mode: str,
    entrypoint: str,
    blocking: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    source = dict(raw or {})
    if "critique_policy" in source and isinstance(source.get("critique_policy"), dict):
        source = dict(source["critique_policy"])

    blocking_items = _clean_blocking(blocking)
    has_blocking = bool(blocking_items)
    critique_mode = "advisory" if str(source.get("critique_mode") or default_mode).strip().lower() == "advisory" else "strict"
    bypass_recorded = bool(source.get("bypass_recorded", False))
    if not bypass_recorded and critique_mode == "strict":
        bypass_recorded = str(source.get("blocking_policy") or "").strip() == "allow_with_recorded_bypass"
    blocks_generation = source.get("blocks_generation")
    if not isinstance(blocks_generation, bool):
        blocks_generation = bool(critique_mode == "strict" and has_blocking and not bypass_recorded)

    return {
        "critique_mode": critique_mode,
        "blocking_policy": str(
            source.get("blocking_policy")
            or (
                "report_only"
                if critique_mode == "advisory"
                else ("allow_with_recorded_bypass" if bypass_recorded else "block_generation")
            )
        ),
        "entrypoint": str(source.get("entrypoint") or entrypoint or ""),
        "has_blocking_issues": bool(source.get("has_blocking_issues", has_blocking)),
        "blocks_generation": blocks_generation,
        "bypass_requested": bool(source.get("bypass_requested", bypass_recorded)),
        "bypass_recorded": bypass_recorded,
        "bypass_reason": str(source.get("bypass_reason") or ""),
        "bypass_recorded_at": str(source.get("bypass_recorded_at") or ""),
    }
