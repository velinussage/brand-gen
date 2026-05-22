from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

# Define the 5 memory tiers
MEMORY_TIERS = ["brand", "campaign", "artifact", "agent", "user"]

def get_memory_dir(brand_dir: Path) -> Path:
    """Gets the memory subdirectory for a brand, ensuring it exists."""
    memory_dir = Path(brand_dir) / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir

def get_ledger_path(brand_dir: Path, tier_name: str) -> Path:
    """Gets the path to the canonical JSONL event ledger for a tier."""
    if tier_name not in MEMORY_TIERS:
        raise ValueError(f"Unknown memory tier: {tier_name}")
    return get_memory_dir(brand_dir) / f"{tier_name}.jsonl"

def get_markdown_path(brand_dir: Path, tier_name: str) -> Path:
    """Gets the path to the derived markdown dossier for a tier."""
    if tier_name not in MEMORY_TIERS:
        raise ValueError(f"Unknown memory tier: {tier_name}")
    return get_memory_dir(brand_dir) / f"{tier_name}.md"

def append_event_to_ledger(brand_dir: Path, tier_name: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Appends a new event canonical record to the append-only JSONL ledger."""
    ledger_path = get_ledger_path(brand_dir, tier_name)
    event_record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "payload": payload,
    }
    
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_record) + "\n")
        
    return event_record

def read_ledger_events(brand_dir: Path, tier_name: str) -> list[dict[str, Any]]:
    """Reads and parses all events from the tier ledger sequentially."""
    ledger_path = get_ledger_path(brand_dir, tier_name)
    if not ledger_path.exists():
        return []
        
    events = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events

# Summarization registry to avoid circular imports
_SUMMARIZERS = {}

def register_summarizer(tier_name: str, func):
    """Registers the summarization rendering function for a tier."""
    _SUMMARIZERS[tier_name] = func

def trigger_summarization(brand_dir: Path, tier_name: str) -> None:
    """Triggers the derived markdown rendering for a tier if a summarizer is registered."""
    if tier_name in _SUMMARIZERS:
        try:
            _SUMMARIZERS[tier_name](brand_dir)
        except Exception as exc:
            print(f"Warning: Failed to run summarizer for {tier_name}: {exc}")

def trigger_all_summarizations(brand_dir: Path) -> None:
    """Triggers derived markdown rendering across all 5 tiers."""
    for tier in MEMORY_TIERS:
        trigger_summarization(brand_dir, tier)


def _ensure_tier_summarizers_registered() -> None:
    """Imports each tier module so its register_summarizer call fires."""
    from brand_gen.memory import agent, artifact, brand, campaign, user  # noqa: F401


_ensure_tier_summarizers_registered()
