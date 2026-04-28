"""Typed pipeline artifacts for brand-gen.

Lightweight dataclass-based wrappers around existing JSON artifacts.
These are intentionally permissive read-only adapters so legacy files
remain valid.
"""

from __future__ import annotations

import time
import uuid
from hashlib import sha256
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
    render_backend: str = "native"
    source_url: str = ""
    entity_type: str = ""
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
class VariantSpec:
    variant_id: str
    label: str = ""
    archetype: str = ""
    capsule: str = ""
    design_variance: int = 5
    visual_thesis: str = ""
    selection_score: float = 0.0
    selection_reasons: list[str] = field(default_factory=list)
    difference_axes: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.variant_id:
            raise ValueError("variant_id is required")
        if not (1 <= int(self.design_variance) <= 10):
            raise ValueError("design_variance must be 1-10")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "VariantSpec":
        payload = dict(raw or {})
        variant_id = str(payload.get("variant_id") or payload.get("id") or payload.get("capsule_id") or payload.get("label") or "").strip()
        raw_payload = payload.get("payload")
        return cls(
            variant_id=variant_id,
            label=str(payload.get("label") or variant_id),
            archetype=str(payload.get("archetype") or payload.get("archetype_id") or ""),
            capsule=str(payload.get("capsule") or payload.get("capsule_id") or ""),
            design_variance=int(payload.get("design_variance") or 5),
            visual_thesis=str(payload.get("visual_thesis") or ""),
            selection_score=float(payload.get("selection_score") or 0.0),
            selection_reasons=list(payload.get("selection_reasons") or []),
            difference_axes=list(payload.get("difference_axes") or []),
            payload=dict(raw_payload or {}) if isinstance(raw_payload, dict) else payload,
        )


@dataclass
class AestheticExperiment:
    branch_id: str
    archetype: str
    capsule: str
    design_variance: int
    variants: list[VariantSpec]
    parent_branch_id: str = ""
    selected_variant_index: int = 0
    selection_rationale: str = ""

    def __post_init__(self) -> None:
        if not self.branch_id:
            raise ValueError("branch_id is required")
        if not (1 <= int(self.design_variance) <= 10):
            raise ValueError("design_variance must be 1-10")
        variants = [item if isinstance(item, VariantSpec) else VariantSpec.from_dict(item) for item in (self.variants or [])]
        if not variants:
            raise ValueError("variants must not be empty")
        if not (0 <= int(self.selected_variant_index) < len(variants)):
            raise ValueError("selected_variant_index out of range")
        object.__setattr__(self, "variants", variants)

    @staticmethod
    def stable_branch_id(*, brand_key: str, material_type: str, seed: str, iteration: int | str = 1) -> str:
        raw = "|".join([str(brand_key or ""), str(material_type or ""), str(iteration or ""), str(seed or "")])
        return "br_" + sha256(raw.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AestheticExperiment":
        variants = [VariantSpec.from_dict(item) if isinstance(item, dict) else item for item in (raw.get("variants") or [])]
        return cls(
            branch_id=str(raw.get("branch_id") or ""),
            parent_branch_id=str(raw.get("parent_branch_id") or ""),
            archetype=str(raw.get("archetype") or ""),
            capsule=str(raw.get("capsule") or ""),
            design_variance=int(raw.get("design_variance") or 5),
            variants=variants,  # type: ignore[arg-type]
            selected_variant_index=int(raw.get("selected_variant_index") or 0),
            selection_rationale=str(raw.get("selection_rationale") or ""),
        )


@dataclass
class MaterialPlan:
    material_type: str
    mode: str = "hybrid"
    workflow_id: str = ""
    render_backend: str = "native"
    source_url: str = ""
    entity_type: str = ""
    purpose: str = ""
    target_surface: str = ""
    product_truth_expression: str = ""
    source_shape: str = ""
    exact_text_required: bool = False
    selected_surface_strategy: str = ""
    selected_surface_strategy_label: str = ""
    selected_surface_strategy_summary: str = ""
    selected_surface_strategy_layout_family: str = ""
    selected_surface_strategy_prompt_directive: str = ""
    surface_strategy_reason: str = ""
    surface_strategy_candidates: list[dict[str, Any]] = field(default_factory=list)
    abstraction_level: str = "medium"
    system_mechanic: str | None = None
    preserve: list[str] = field(default_factory=list)
    push: list[str] = field(default_factory=list)
    ban: list[str] = field(default_factory=list)
    prompt_seed: str = ""
    role_pack: RolePack | None = None
    brand_anchor_policy: dict[str, Any] = field(default_factory=dict)
    inspiration_board: dict[str, Any] = field(default_factory=dict)
    selected_reference_ids: list[str] = field(default_factory=list)
    selected_inspiration_ids: list[str] = field(default_factory=list)
    selected_inspiration_source_keys: list[str] = field(default_factory=list)
    selected_inspiration_sources: list[dict[str, Any]] = field(default_factory=list)
    selected_mechanic_ids: list[str] = field(default_factory=list)
    selected_mechanic_labels: list[str] = field(default_factory=list)
    selected_inspiration_translation: str = ""
    inspiration_selection_reason: str = ""
    inspiration_selection_mode: str = ""
    reference_image_count: int = 0
    has_motion_reference: bool = False
    set_scope: bool = False
    design_variance: int = 5
    material_prompt_profile: dict[str, Any] = field(default_factory=dict)
    product_truth_contract: str = ""
    product_truth_validation: dict[str, Any] = field(default_factory=dict)
    sage_vault_brief: dict[str, Any] = field(default_factory=dict)
    sage_generation_contract: dict[str, Any] = field(default_factory=dict)
    aesthetic_capsule: dict[str, Any] | None = None
    aesthetic_capsule_id: str = ""
    aesthetic_capsule_selection: dict[str, Any] = field(default_factory=dict)
    aesthetic_direction_brief: dict[str, Any] = field(default_factory=dict)
    aesthetic_style_strength: float | int | None = None
    aesthetic_reference_roles: dict[str, Any] = field(default_factory=dict)
    branch_id: str = ""
    parent_branch_id: str = ""
    selected_direction_id: str = ""
    experiment: AestheticExperiment | None = None

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
    critique_policy: dict[str, Any] = field(default_factory=dict)
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
    execution_prompt: str = ""
    execution: ExecutionParams = field(default_factory=ExecutionParams)
    checks: CritiqueChecks = field(default_factory=CritiqueChecks)
    critique_policy: dict[str, Any] = field(default_factory=dict)
    reference_analysis_mode: str = ""
    reference_analysis_confidence: str = ""
    reference_paths: list[str] = field(default_factory=list)
    inspiration_board: dict[str, Any] = field(default_factory=dict)
    selected_reference_ids: list[str] = field(default_factory=list)
    selected_inspiration_ids: list[str] = field(default_factory=list)
    selected_mechanic_ids: list[str] = field(default_factory=list)
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
    agent_review_path: str = ""
    critique_policy: dict[str, Any] = field(default_factory=dict)
    vlm_critique: VLMCritique | None = None
    visual_review_status: str = ""
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
    source_version: str = ""
    branch_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NextAction:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class PrepareRunResponse:
    run_id: str
    brand_dna_summary: dict[str, Any] = field(default_factory=dict)
    applicable_learnings: dict[str, Any] = field(default_factory=dict)
    readiness_issues: list[str] = field(default_factory=list)
    route: dict[str, Any] = field(default_factory=dict)
    next_action: NextAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanRunResponse:
    run_id: str
    plan_id: str = ""
    plan_summary: dict[str, Any] = field(default_factory=dict)
    next_action: NextAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidateRunResponse:
    run_id: str
    status: str = "ok"
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    critique_id: str = ""
    critique_policy: dict[str, Any] = field(default_factory=dict)
    next_action: NextAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecuteRunResponse:
    run_id: str
    version_id: str = ""
    image_paths: list[str] = field(default_factory=list)
    stopped_at: str = ""
    scratchpad_path: str = ""
    review_packet_path: str = ""
    quality_gate: dict[str, Any] = field(default_factory=dict)
    iterations: int = 1
    all_versions: list[str] = field(default_factory=list)
    next_action: NextAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewRunResponse:
    run_id: str
    version_id: str
    packet_id: str = ""
    axis_scores: dict[str, Any] = field(default_factory=dict)
    decision: str = ""
    before_after_diffs: list[dict[str, Any]] = field(default_factory=list)
    visual_review_status: str = ""
    auto_review_path: str = ""
    agent_review_path: str = ""
    next_action: NextAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvolveRunResponse:
    run_id: str
    version_id: str = ""
    learnings_promoted: list[dict[str, Any]] = field(default_factory=list)
    disagreements_logged: int = 0
    recommendation: str = ""
    identity_rebuild_recommended: bool = False
    improvement_questions: list[dict[str, Any]] = field(default_factory=list)
    next_action: NextAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestrateMaterialResponse:
    run_id: str
    stages_completed: list[str] = field(default_factory=list)
    stop_reason: str = ""
    next_action: NextAction | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)

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
    if isinstance(plan_fields.get("experiment"), dict):
        plan_fields["experiment"] = AestheticExperiment.from_dict(plan_fields["experiment"])
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
        critique_policy=dict(d.get("critique_policy") or {}),
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
        execution_prompt=str(d.get("execution_prompt") or d.get("effective_prompt", "")),
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
        critique_policy=dict(d.get("critique_policy") or {}),
        reference_analysis_mode=str(d.get("reference_analysis_mode", "")),
        reference_analysis_confidence=str(d.get("reference_analysis_confidence", "")),
        reference_paths=list(
            ref_ctx.get("all_context_refs")
            or ref_ctx.get("authoritative_reference_paths")
            or ref_ctx.get("model_transport_reference_paths")
            or ref_ctx.get("passed_reference_paths")
            or d.get("reference_paths")
            or []
        ),
        inspiration_board=dict(d.get("inspiration_board") or {}),
        selected_reference_ids=list(d.get("selected_reference_ids") or ref_ctx.get("selected_reference_ids") or []),
        selected_inspiration_ids=list(d.get("selected_inspiration_ids") or ref_ctx.get("selected_inspiration_ids") or []),
        selected_mechanic_ids=list(d.get("selected_mechanic_ids") or []),
        plan=d.get("plan") or {},
        plan_critique=d.get("plan_critique") or {},
        brand_dir=str(d.get("brand_dir", "")),
        output_path=str(d.get("output_path", "")),
    )
