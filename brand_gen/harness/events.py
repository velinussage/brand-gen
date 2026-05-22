"""Campaign-aware run ledger schema representing active runs and workflow stages."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunEvent:
    """Dataclass mapping to the extended campaign-aware run_ledger schema.
    
    Contains execution details, model parameters, costs, and state branch info.
    """

    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    run_id: str = ""
    campaign_id: str = ""
    workflow_id: str = ""
    stage: str = ""
    event_type: str = ""
    attempt_id: str = ""
    material_type: str = ""
    mode: str = ""
    recommended_route: str = ""
    chosen_route: str = ""
    route_scores: dict[str, Any] = field(default_factory=dict)
    selected_reference_paths: list[str] = field(default_factory=list)
    selected_reference_ids: list[str] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    prompt_hash: str = ""
    source_version: str = ""
    output_version: str = ""
    cost: float | None = None
    duration_ms: int | None = None
    status: str = ""
    notes: str = ""
    warnings: list[str] = field(default_factory=list)
    branch_id: str = ""
    parent_branch_id: str = ""
    branch_status: str = ""
    selected_direction_id: str = ""
    override_reason: str = ""
    override_actor: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    schema_type: str = "run_event"
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize the RunEvent instance to a dictionary."""
        return {
            "schema_type": self.schema_type,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "campaign_id": self.campaign_id,
            "workflow_id": self.workflow_id,
            "stage": self.stage,
            "event_type": self.event_type,
            "attempt_id": self.attempt_id,
            "material_type": self.material_type,
            "mode": self.mode,
            "recommended_route": self.recommended_route,
            "chosen_route": self.chosen_route,
            "route_scores": self.route_scores,
            "selected_reference_paths": self.selected_reference_paths,
            "selected_reference_ids": self.selected_reference_ids,
            "model": self.model,
            "provider": self.provider,
            "prompt_hash": self.prompt_hash,
            "source_version": self.source_version,
            "output_version": self.output_version,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "notes": self.notes,
            "warnings": self.warnings,
            "branch_id": self.branch_id,
            "parent_branch_id": self.parent_branch_id,
            "branch_status": self.branch_status,
            "selected_direction_id": self.selected_direction_id,
            "override_reason": self.override_reason,
            "override_actor": self.override_actor,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunEvent:
        """Deserialize a dictionary to a RunEvent instance."""
        return cls(
            schema_type=data.get("schema_type", "run_event"),
            schema_version=data.get("schema_version", 1),
            timestamp=data.get("timestamp", ""),
            run_id=data.get("run_id", ""),
            campaign_id=data.get("campaign_id", ""),
            workflow_id=data.get("workflow_id", ""),
            stage=data.get("stage", ""),
            event_type=data.get("event_type", ""),
            attempt_id=data.get("attempt_id", ""),
            material_type=data.get("material_type", ""),
            mode=data.get("mode", ""),
            recommended_route=data.get("recommended_route", ""),
            chosen_route=data.get("chosen_route", ""),
            route_scores=data.get("route_scores") or {},
            selected_reference_paths=data.get("selected_reference_paths") or [],
            selected_reference_ids=data.get("selected_reference_ids") or [],
            model=data.get("model", ""),
            provider=data.get("provider", ""),
            prompt_hash=data.get("prompt_hash", ""),
            source_version=data.get("source_version", ""),
            output_version=data.get("output_version", ""),
            cost=data.get("cost"),
            duration_ms=data.get("duration_ms"),
            status=data.get("status", ""),
            notes=data.get("notes", ""),
            warnings=data.get("warnings") or [],
            branch_id=data.get("branch_id", ""),
            parent_branch_id=data.get("parent_branch_id", ""),
            branch_status=data.get("branch_status", ""),
            selected_direction_id=data.get("selected_direction_id", ""),
            override_reason=data.get("override_reason", ""),
            override_actor=data.get("override_actor", ""),
            data=data.get("data") or {},
        )
