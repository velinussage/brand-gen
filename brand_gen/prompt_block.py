"""Typed prompt blocks for priority-tier eviction."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptBlock:
    id: str
    text: str
    priority: int
    constraint_type: str = "soft"
    provenance: str = ""
    budget_chars: int = 0
    stage: str = "brief"


SECTION_PRIORITY: dict[str, int] = {
    "brand_anchor_rule": 0,
    "critical_bans": 5,
    "explicit_copy_rule": 10,
    "material_policy": 20,
    "aesthetic_commitment_block": 25,
    "rubric_overlay_push": 30,
    "reference_analysis_caveat": 35,
    "five_slot_brief": 40,
    "visual_density_block": 45,
    "aesthetic_archetype_block": 50,
    "role_pack_block": 80,
    "selected_inspiration_block": 85,
}

SECTION_STAGE: dict[str, str] = {
    "brand_anchor_rule": "system",
    "critical_bans": "system",
    "explicit_copy_rule": "system",
    "material_policy": "contract",
    "aesthetic_commitment_block": "contract",
    "rubric_overlay_push": "contract",
    "reference_analysis_caveat": "contract",
    "five_slot_brief": "brief",
    "visual_density_block": "brief",
    "aesthetic_archetype_block": "brief",
    "role_pack_block": "examples",
    "selected_inspiration_block": "examples",
}

SECTION_CONSTRAINT: dict[str, str] = {
    "brand_anchor_rule": "hard",
    "critical_bans": "hard",
    "explicit_copy_rule": "hard",
}


def blocks_from_sections(sections: dict[str, str]) -> list[PromptBlock]:
    out: list[PromptBlock] = []
    for section_id, text in sections.items():
        if section_id == "body":
            continue
        out.append(
            PromptBlock(
                id=section_id,
                text=str(text or ""),
                priority=SECTION_PRIORITY.get(section_id, 60),
                constraint_type=SECTION_CONSTRAINT.get(section_id, "soft"),
                provenance="prompt_assembly",
                stage=SECTION_STAGE.get(section_id, "brief"),
            )
        )
    return out


def evict_to_budget(
    blocks: list[PromptBlock],
    budget_chars: int,
    *,
    separator_chars: int = 2,
) -> tuple[list[PromptBlock], list[PromptBlock]]:
    active = [block for block in blocks if block.text.strip()]
    total = sum(len(block.text) for block in active) + max(0, len(active) - 1) * separator_chars
    if total <= budget_chars:
        return active, []

    candidates = sorted(
        [(idx, block) for idx, block in enumerate(active) if block.constraint_type != "hard"],
        key=lambda item: (-item[1].priority, -item[0]),
    )
    dropped_indices: set[int] = set()
    dropped: list[PromptBlock] = []
    for original_idx, block in candidates:
        if total <= budget_chars:
            break
        total -= len(block.text) + separator_chars
        dropped_indices.add(original_idx)
        dropped.append(block)

    kept = [block for idx, block in enumerate(active) if idx not in dropped_indices]
    return kept, dropped
