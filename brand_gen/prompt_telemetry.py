"""Per-generation prompt compression telemetry.

The buffer is context-local so tests and concurrent generations do not leak
cap/drop events into each other.  Callers explicitly clear before assembly and
drain after the scratchpad prompt is built.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any


_BUFFER: ContextVar[list[dict[str, Any]] | None] = ContextVar("prompt_compression_telemetry", default=None)


def clear_prompt_telemetry() -> None:
    _BUFFER.set([])


def _buffer() -> list[dict[str, Any]]:
    current = _BUFFER.get()
    if current is None:
        current = []
        _BUFFER.set(current)
    return current


def record_cap(
    *,
    site_id: str,
    block_name: str,
    original_text: str,
    capped_text: str,
    max_chars: int | float,
    pre_priority: bool,
    stage: str,
) -> None:
    original = str(original_text or "")
    capped = str(capped_text or "")
    if len(capped) >= len(original):
        return
    _buffer().append(
        {
            "kind": "cap_text_at_sentence",
            "site_id": site_id,
            "block_name": block_name,
            "stage": stage,
            "original_chars": len(original),
            "capped_chars": len(capped),
            "limit": int(max_chars),
            "pre_priority": bool(pre_priority),
        }
    )


def record_compression(
    *,
    block_name: str,
    original_chars: int,
    compressed_chars: int,
    max_chars: int | float,
    max_sentences: int | float,
    pre_priority: bool,
    stage: str,
) -> None:
    if compressed_chars >= original_chars:
        return
    _buffer().append(
        {
            "kind": "compress_prompt_body",
            "site_id": "prompt_assembly.compress_prompt_body",
            "block_name": block_name,
            "stage": stage,
            "original_chars": int(original_chars),
            "capped_chars": int(compressed_chars),
            "limit": int(max_chars),
            "max_sentences": int(max_sentences),
            "pre_priority": bool(pre_priority),
        }
    )


def record_eviction(*, block: Any, budget_chars: int, total_before: int) -> None:
    _buffer().append(
        {
            "kind": "dropped_block",
            "site_id": "prompt_block.evict_to_budget",
            "block_name": str(getattr(block, "id", "") or ""),
            "stage": str(getattr(block, "stage", "") or ""),
            "priority": int(getattr(block, "priority", 60)),
            "constraint_type": str(getattr(block, "constraint_type", "soft") or "soft"),
            "original_chars": int(getattr(block, "text", "") and len(getattr(block, "text", "")) or 0),
            "capped_chars": 0,
            "limit": int(budget_chars),
            "total_before": int(total_before),
            "pre_priority": False,
        }
    )


def get_prompt_telemetry() -> list[dict[str, Any]]:
    return [dict(item) for item in (_BUFFER.get() or [])]


def drain_prompt_telemetry() -> list[dict[str, Any]]:
    items = get_prompt_telemetry()
    _BUFFER.set([])
    return items
