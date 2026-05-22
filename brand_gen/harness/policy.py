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
    """Execution policy limits and safety/approval rules for active runs.

    Default allowed_models tracks the current best-in-class options on
    Replicate as of 2026-05; the generator persona picks per-prompt from
    this list given prompt characteristics + budget. Override per-campaign
    when a brand prefers a specific style profile.

    Image: nano-banana-2 (Google, low-cost edit/ref), flux-2-pro (BFL,
           multi-ref + text), flux-2-flex (BFL, typography-heavy),
           recraft-v4 (vector + editorial), runway-gen4-image (campaign).
    Video: kling-v2.6 (logo/edge preservation), seedance-2-pro (motion),
           veo (cinematic, audio).
    """

    max_generations: int = 5
    max_cost_estimate: float = 4.0
    allowed_models: list[str] = field(default_factory=lambda: [
        # Image — latest fast/reference models
        "nano-banana-2",
        "flux-2-pro",
        "flux-2-flex",
        "recraft-v4",
        "runway-gen4-image",
        # Video — latest motion/cinematic models
        "kling-v2.6",
        "seedance-2-pro",
        "veo",
    ])
    allowed_tools: list[str] = field(default_factory=list)
    approval_triggers: list[ApprovalTrigger] = field(default_factory=list)
