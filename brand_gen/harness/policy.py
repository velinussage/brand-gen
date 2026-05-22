"""Approval triggering and policy definitions for Q6 sync/async gates."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ApprovalTrigger:
    """Represents a policy gate for sensitive or costly actions."""

    name: Literal[
        "pre_paid_generation",
        "pre_brand_memory_mutation",
        "pre_export_publish",
        "pre_overwrite_locked_material",
        "pre_branch_abandon",
    ]
    mode: Literal["sync", "async"]
    budget_threshold: float | None = None


@dataclass(frozen=True)
class RunPolicy:
    """Execution policy limits and safety/approval rules for active runs."""

    max_generations: int = 5
    max_cost_estimate: float = 4.0
    allowed_models: list[str] = field(default_factory=lambda: ["flux-2-pro", "kling"])
    allowed_tools: list[str] = field(default_factory=list)
    approval_triggers: list[ApprovalTrigger] = field(default_factory=list)
