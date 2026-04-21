"""MemoryService — durable taste accumulation facade.

Wraps three persistence modules behind a class interface so typed
callers have one API to read learnings, iteration memory, and
inspiration memory without caring how each is stored.

Layer contract (Phase 6):
  - Reads are the primary path; mutations go through typed CLI tools
    (see brand_gen/commands/state.py and brand_gen/commands/identity.py
    for the mutation verbs). This service is not a write surface.
  - Rotation state (recent_style_anchors_by_material,
    recent_archetypes_by_material) is ORCHESTRATION state, not memory
    state — it lives on OrchestrationService, not here.
  - Does not import OrchestrationService or PromptResolver. Callers
    that need both compose at the call site.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..inspiration_memory import load_inspiration_memory
from ..iteration_memory import load_iteration_memory
from ..learnings_memory import load_learnings_memory, summarize_learnings_memory


class MemoryService:
    """Facade over learnings.json, iteration-memory.json, and
    inspiration-memory.json. Instantiate per brand_dir.

    All reads are idempotent and safe to call repeatedly.
    """

    def __init__(self, brand_dir: Path) -> None:
        self.brand_dir = Path(brand_dir)

    # ── Learnings ────────────────────────────────────────────────────

    def load_learnings(self) -> dict[str, Any]:
        """Raw learnings.json. Includes modelPreferences,
        styleReferencePolicies, failurePatterns, compositionPatterns,
        colorInsights, messagingInsights, audienceInsights.
        """
        return load_learnings_memory(self.brand_dir)

    def summarize_learnings(self) -> dict[str, Any]:
        """Compact summary suitable for prompt context or review."""
        return summarize_learnings_memory(load_learnings_memory(self.brand_dir))

    def model_preferences_for(self, material_type: str) -> list[dict[str, Any]]:
        """Filter modelPreferences bucket by material_type (hyphen or
        underscore form — matches both because of the 2026-04-21 migration).
        """
        material = (material_type or "").strip().lower()
        variants = {material, material.replace("-", "_"), material.replace("_", "-")}
        learnings = load_learnings_memory(self.brand_dir)
        entries = learnings.get("modelPreferences") or []
        return [
            entry
            for entry in entries
            if str(entry.get("material_type") or "").lower() in variants
        ]

    def style_reference_policies_for(self, material_type: str) -> list[dict[str, Any]]:
        material = (material_type or "").strip().lower()
        variants = {material, material.replace("-", "_"), material.replace("_", "-")}
        learnings = load_learnings_memory(self.brand_dir)
        entries = learnings.get("styleReferencePolicies") or []
        policies: list[dict[str, Any]] = []
        for entry in entries:
            mat = str(entry.get("material_type") or "").lower()
            applies = {
                str(item).lower()
                for item in (entry.get("applies_to_material_types") or [])
            }
            if mat in variants or (applies & variants):
                policies.append(entry)
        return policies

    # ── Iteration memory ─────────────────────────────────────────────

    def load_iteration_memory(self) -> dict[str, Any]:
        """Raw iteration-memory.json. Positive/negative examples,
        material-specific notes.

        Note: rotation-state fields (last_style_anchor_by_material,
        recent_style_anchors_by_material, recent_archetypes_by_material)
        are surfaced here for compatibility, but conceptually belong on
        OrchestrationService. New callers should prefer
        OrchestrationService.rotation_state().
        """
        return load_iteration_memory(self.brand_dir)

    def negative_examples(self, limit: int | None = None) -> list[dict[str, Any]]:
        memory = load_iteration_memory(self.brand_dir)
        items = list(memory.get("negative_examples") or [])
        return items[-limit:] if limit else items

    def positive_examples(self, limit: int | None = None) -> list[dict[str, Any]]:
        memory = load_iteration_memory(self.brand_dir)
        items = list(memory.get("positive_examples") or [])
        return items[-limit:] if limit else items

    # ── Inspiration memory ───────────────────────────────────────────

    def load_inspiration_memory(self) -> dict[str, Any]:
        """Raw inspiration-memory.json; empty dict when absent."""
        try:
            return load_inspiration_memory(self.brand_dir)
        except FileNotFoundError:
            return {}

    def inspiration_sources(self) -> list[dict[str, Any]]:
        """List of configured inspiration source records with their
        primary_bucket / bucket_scores / bucket_hints (from the
        rebucket-inspiration command).
        """
        payload = self.load_inspiration_memory()
        return list(payload.get("sources") or [])

    # ── Aggregate view ───────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """One-call payload for agents that want everything at once.
        Cheap to call; all three reads hit local JSON.
        """
        return {
            "brand_dir": str(self.brand_dir),
            "learnings_summary": self.summarize_learnings(),
            "iteration_memory": self.load_iteration_memory(),
            "inspiration_sources": self.inspiration_sources(),
        }
