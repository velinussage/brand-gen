"""Typed pipeline artifacts for brand-gen.

Lightweight dataclass-based wrappers around existing JSON artifacts.
These are intentionally permissive read-only adapters so legacy files
remain valid.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WorkflowMeta:
    workflow_id: str
    stage: str
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    previous_stage_path: str | None = None

    @staticmethod
    def new(stage: str) -> "WorkflowMeta":
        return WorkflowMeta(workflow_id=uuid.uuid4().hex[:12], stage=stage)


@dataclass
class RoutingBrief:
    material_type: str | None = None
    material_key: str | None = None
    goal: str = ""
    request: str = ""
    has_motion_reference: bool = False
    set_scope: bool = False
    reference_image_count: int = 0
    mode: str | None = None


@dataclass
class RouteDecision:
    meta: WorkflowMeta
    route_key: str
    route_label: str = ""
    score: float = 0.0
    method: str = "predicate"
    score_vector: dict[str, float] = field(default_factory=dict)
    specialists: list[str] = field(default_factory=list)
    next_commands: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class RolePackEntry:
    role: str
    source_key: str = ""
    source_name: str = ""
    path: str = ""
    translation: dict[str, Any] = field(default_factory=dict)


@dataclass
class RolePack:
    selected_roles: list[RolePackEntry] = field(default_factory=list)
    required_roles: list[str] = field(default_factory=list)


@dataclass
class MaterialPlan:
    material_type: str
    mode: str = "hybrid"
    purpose: str = ""
    target_surface: str = ""
    product_truth_expression: str = ""
    abstraction_level: str = "medium"
    system_mechanic: str | None = None
    preserve: list[str] = field(default_factory=list)
    push: list[str] = field(default_factory=list)
    ban: list[str] = field(default_factory=list)
    prompt_seed: str = ""
    role_pack: RolePack | None = None
    brand_anchor_policy: dict[str, Any] = field(default_factory=dict)
    reference_image_count: int = 0
    has_motion_reference: bool = False
    set_scope: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.mode not in ("reference", "inspiration", "hybrid"):
            errors.append(f"Invalid mode '{self.mode}': must be reference/inspiration/hybrid")
        if not self.material_type:
            errors.append("material_type is required")
        return errors


@dataclass
class PlanDraft:
    meta: WorkflowMeta
    plan: MaterialPlan
    derived: dict[str, Any] = field(default_factory=dict)
    output_path: str = ""


@dataclass
class PlanValidation:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PromptReview:
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class CritiqueChecks:
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PlanCritique:
    meta: WorkflowMeta
    plan_validation: PlanValidation = field(default_factory=PlanValidation)
    prompt_review: PromptReview = field(default_factory=PromptReview)
    checks: CritiqueChecks = field(default_factory=CritiqueChecks)
    plan_path: str = ""
    output_path: str = ""

    @property
    def has_blocking(self) -> bool:
        return bool(self.checks.blocking)

    @property
    def approved(self) -> bool:
        return self.plan_validation.ok and not self.has_blocking


@dataclass
class ExecutionParams:
    model: str = ""
    aspect_ratio: str = "16:9"
    generation_mode: str = "image"
    seed: int | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.model:
            errors.append("model is required")
        return errors


@dataclass
class GenerationScratchpad:
    meta: WorkflowMeta
    material_type: str = ""
    workflow_mode: str = ""
    effective_prompt: str = ""
    execution: ExecutionParams = field(default_factory=ExecutionParams)
    checks: CritiqueChecks = field(default_factory=CritiqueChecks)
    reference_paths: list[str] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    plan_critique: dict[str, Any] = field(default_factory=dict)
    brand_dir: str = ""
    output_path: str = ""

    @property
    def has_blocking(self) -> bool:
        return bool(self.checks.blocking)


@dataclass
class VLMCritique:
    approved: bool = False
    p1: list[str] = field(default_factory=list)
    p2: list[str] = field(default_factory=list)
    p3: list[str] = field(default_factory=list)
    palette_match: float = 0.0
    logo_visible: bool = False
    hallucinated_elements: list[str] = field(default_factory=list)
    refinement_suggestion: str = ""
    vlm_available: bool = False


@dataclass
class GenerationResult:
    meta: WorkflowMeta
    version_id: str = ""
    image_paths: list[str] = field(default_factory=list)
    scratchpad_path: str = ""
    auto_review_path: str = ""
    vlm_critique: VLMCritique | None = None
    iteration: int = 1
    all_versions: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    workflow_id: str
    route: RouteDecision | None = None
    plan_draft: PlanDraft | None = None
    critique: PlanCritique | None = None
    scratchpad: GenerationScratchpad | None = None
    result: GenerationResult | None = None
    stopped_at: str = ""
    stop_reason: str = ""
    iterations: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _filter_fields(raw: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    return {key: value for key, value in raw.items() if key in allowed}


def plan_draft_from_dict(d: dict[str, Any], workflow_id: str) -> PlanDraft:
    plan_data = d.get("plan", d) if isinstance(d, dict) else {}
    role_pack = None
    raw_rp = plan_data.get("role_pack") or {}
    if isinstance(raw_rp, dict):
        selected = []
        for item in raw_rp.get("selected_roles") or raw_rp.get("roles") or []:
            if isinstance(item, dict) and item.get("role"):
                selected.append(RolePackEntry(**_filter_fields(item, set(RolePackEntry.__dataclass_fields__.keys()))))
        role_pack = RolePack(selected_roles=selected, required_roles=list(raw_rp.get("required_roles") or []))
    plan_fields = _filter_fields(plan_data, set(MaterialPlan.__dataclass_fields__.keys()))
    if role_pack is not None:
        plan_fields["role_pack"] = role_pack
    return PlanDraft(
        meta=WorkflowMeta(workflow_id=workflow_id, stage="plan_draft"),
        plan=MaterialPlan(**plan_fields),
        derived=d.get("derived", {}) if isinstance(d, dict) else {},
        output_path=str(d.get("output_path", "")) if isinstance(d, dict) else "",
    )


def critique_from_dict(d: dict[str, Any], workflow_id: str) -> PlanCritique:
    pv = d.get("plan_validation") or {}
    pr = d.get("prompt_review") or {}
    ch = d.get("checks") or {}
    return PlanCritique(
        meta=WorkflowMeta(workflow_id=workflow_id, stage="critique"),
        plan_validation=PlanValidation(
            ok=bool(pv.get("ok", True)),
            errors=list(pv.get("errors") or []),
            warnings=list(pv.get("warnings") or []),
        ),
        prompt_review=PromptReview(
            issues=list(pr.get("issues") or []),
            recommendations=list(pr.get("recommendations") or []),
        ),
        checks=CritiqueChecks(
            blocking=list(ch.get("blocking") or []),
            warnings=list(ch.get("warnings") or []),
        ),
        plan_path=str(d.get("plan_path", "")),
        output_path=str(d.get("output_path", "")),
    )


def scratchpad_from_dict(d: dict[str, Any], workflow_id: str) -> GenerationScratchpad:
    ex = d.get("execution") or {}
    ch = d.get("checks") or {}
    ref_ctx = d.get("reference_context") or {}
    return GenerationScratchpad(
        meta=WorkflowMeta(workflow_id=workflow_id, stage="scratchpad"),
        material_type=str(d.get("material_type", "")),
        workflow_mode=str(d.get("workflow_mode", "")),
        effective_prompt=str(d.get("effective_prompt", "")),
        execution=ExecutionParams(
            model=str(ex.get("model", "")),
            aspect_ratio=str(ex.get("aspect_ratio", "16:9")),
            generation_mode=str(d.get("generation_mode") or ex.get("generation_mode") or "image"),
            seed=ex.get("seed"),
        ),
        checks=CritiqueChecks(
            blocking=list(ch.get("blocking") or []),
            warnings=list(ch.get("warnings") or []),
        ),
        reference_paths=list(ref_ctx.get("all_context_refs") or ref_ctx.get("passed_reference_paths") or d.get("reference_paths") or []),
        plan=d.get("plan") or {},
        plan_critique=d.get("plan_critique") or {},
        brand_dir=str(d.get("brand_dir", "")),
        output_path=str(d.get("output_path", "")),
    )
