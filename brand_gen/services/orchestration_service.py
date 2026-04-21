"""OrchestrationService — per-run state + rotation + stage events facade.

Separates orchestration-state concerns from durable memory:

  - blackboard.json projection over the run ledger
  - rotation windows for style anchors and archetypes (currently stored
    on iteration_memory.json but conceptually orchestration state)
  - stage event emission helpers that callers use to signal run
    progress without reaching into run_ledger directly

Does NOT import MemoryService or PromptResolver. Callers that span
layers compose at the call site.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..aesthetic_archetypes import (
    pick_rotating_archetype,
    record_archetype_choice,
)
from ..blackboard import (
    append_blackboard_decision,
    load_blackboard,
    save_blackboard,
)
from ..iteration_memory import (
    load_iteration_memory,
    pick_rotating_style_anchor,
    record_style_anchor_choice,
    save_iteration_memory,
)
from ..run_ledger import append_run_event


class OrchestrationService:
    """Facade over blackboard + run ledger + rotation state.

    Instantiate per brand_dir. Stage-emission helpers take a
    `workflow_id` (same id used by PipelineRunner).
    """

    def __init__(self, brand_dir: Path) -> None:
        self.brand_dir = Path(brand_dir)

    # ── Blackboard (current active brief + decisions) ────────────────

    def load_blackboard(self) -> dict[str, Any]:
        return load_blackboard(self.brand_dir)

    def summarize(self) -> dict[str, Any]:
        """Compact summary of the current blackboard for agents that just
        need active brief + latest decisions without the full payload.
        """
        board = load_blackboard(self.brand_dir)
        decisions = board.get("decisions") or []
        return {
            "active_brief": board.get("active_brief") or {},
            "latest_decisions": list(decisions[-5:]),
            "workflow_id": board.get("workflow_id") or "",
            "last_version_id": board.get("last_version_id") or "",
        }

    def append_decision(
        self,
        board: dict[str, Any],
        *,
        agent: str,
        decision: str,
        data: dict[str, Any] | None = None,
        workflow_id: str | None = None,
    ) -> dict[str, Any]:
        """Append a decision without persisting — caller is responsible
        for save_blackboard() when the full set of mutations is ready.
        """
        return append_blackboard_decision(
            board,
            agent=agent,
            decision=decision,
            data=data,
            workflow_id=workflow_id,
        )

    def save(self, board: dict[str, Any]) -> Path:
        return save_blackboard(self.brand_dir, board)

    # ── Rotation state (style anchors + archetypes) ──────────────────

    def pick_style_anchor(
        self,
        policy: dict,
        *,
        material_type: str | None = None,
    ) -> str | None:
        memory = load_iteration_memory(self.brand_dir)
        return pick_rotating_style_anchor(policy, memory, material_type=material_type)

    def record_style_anchor(
        self,
        *,
        material_type: str,
        anchor_version: str,
        anchor_set_size: int | None = None,
    ) -> None:
        memory = load_iteration_memory(self.brand_dir)
        memory = record_style_anchor_choice(
            memory,
            material_type=material_type,
            anchor_version=anchor_version,
            anchor_set_size=anchor_set_size,
        )
        save_iteration_memory(self.brand_dir, memory)

    def pick_archetype(self, material_type: str | None) -> dict | None:
        memory = load_iteration_memory(self.brand_dir)
        return pick_rotating_archetype(material_type, memory)

    def record_archetype(
        self,
        *,
        material_type: str,
        archetype_id: str,
        archetype_set_size: int | None = None,
    ) -> None:
        memory = load_iteration_memory(self.brand_dir)
        memory = record_archetype_choice(
            memory,
            material_type=material_type,
            archetype_id=archetype_id,
            archetype_set_size=archetype_set_size,
        )
        save_iteration_memory(self.brand_dir, memory)

    def rotation_state(self, material_type: str) -> dict[str, Any]:
        """Summarize rotation state for a material — the recent
        style-anchor window and recent-archetype window. Useful for
        debugging why a given anchor was picked.
        """
        memory = load_iteration_memory(self.brand_dir)
        material = str(material_type or "").strip().lower().replace("_", "-")
        return {
            "material_type": material,
            "recent_style_anchors": list(
                (memory.get("recent_style_anchors_by_material") or {}).get(material) or []
            ),
            "last_style_anchor": (
                memory.get("last_style_anchor_by_material") or {}
            ).get(material),
            "recent_archetypes": list(
                (memory.get("recent_archetypes_by_material") or {}).get(material) or []
            ),
        }

    # ── Stage-event emission ─────────────────────────────────────────

    def emit_stage_event(
        self,
        *,
        workflow_id: str,
        stage: str,
        event_type: str,
        status: str = "",
        notes: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Typed wrapper around brand_gen.run_ledger.append_run_event so
        orchestration callers have one entry point for stage signals.

        Typical event_type values:
          prepare_run_started / prepare_run_completed
          plan_run_started / plan_run_completed
          validate_run_started / validate_run_completed
          execute_run_started / execute_run_completed
          review_run_started / review_run_completed
          evolve_run_started / evolve_run_completed
          blocking_finding_raised / blocking_finding_cleared
        """
        append_run_event(
            self.brand_dir,
            workflow_id,
            stage=stage,
            event_type=event_type,
            status=status,
            notes=notes,
            data=data,
        )
