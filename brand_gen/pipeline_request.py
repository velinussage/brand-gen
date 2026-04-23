from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


PIPELINE_MCP_PROPERTIES: dict[str, dict[str, Any]] = {
    "material_type": {"type": "string", "description": "Material type to generate (e.g. social, browser-illustration, landing-hero, logo)"},
    "render_backend": {"type": "string", "enum": ["native", "html"], "default": "native", "description": "Rendering backend. Use html for share-card oriented HTML/layout generation backed by structured page payloads."},
    "mode": {"type": "string", "enum": ["reference", "inspiration", "hybrid"], "default": "hybrid", "description": "Workflow mode for the plan"},
    "tag": {"type": "string", "description": "Optional short output tag for filenames and version metadata."},
    "prompt_seed": {"type": "string", "description": "Optional explicit prompt seed; otherwise one is generated"},
    "mechanic": {"type": "string", "description": "The one system mechanic or reveal move to emphasize"},
    "purpose": {"type": "string", "description": "What job this material should do"},
    "target_surface": {"type": "string", "description": "Where this material will be used"},
    "product_truth_expression": {"type": "string", "description": "What concrete product truth this material must express"},
    "abstraction_level": {"type": "string", "enum": ["low", "medium", "high"], "description": "How abstract this material is allowed to be"},
    "goal": {"type": "string", "description": "Optional top-level goal used for routing context"},
    "request": {"type": "string", "description": "Optional request text used for routing context"},
    "briefing": {"type": "string", "description": "Creative brief text passed to the plan draft stage"},
    "audience": {"type": "string", "description": "Target audience summary"},
    "motion_reference": {"type": "string", "description": "Optional motion reference path for routing or video generation"},
    "base_image": {"type": "string", "description": "Path to an image to edit/overlay on. The model will use this as the base and apply brand overlays, text, icons per the prompt. Auto-selects flux-2-pro."},
    "source_url": {"type": "string", "description": "Optional real product/app URL to extract structured share-card text/details from."},
    "entity_type": {"type": "string", "description": "Optional entity type for HTML share cards (prompt, skill, library, proposal, community, dao, update)."},
    "headline": {"type": "string", "description": "Optional explicit share-card headline override."},
    "subhead": {"type": "string", "description": "Optional explicit share-card subhead override."},
    "cta": {"type": "string", "description": "Optional CTA label override for HTML share cards."},
    "proof_title": {"type": "string", "description": "Optional explicit proof-module title override."},
    "proof_excerpt": {"type": "string", "description": "Optional explicit proof-module excerpt override."},
    "proof_row": {"type": "string", "description": "Optional explicit proof-module footer/detail row override."},
    "proof_meta": {"type": "array", "items": {"type": "string"}, "description": "Optional repeatable proof metadata rows/chips for HTML share cards."},
    "proof_crop_path": {"type": "string", "description": "Optional screenshot crop or product image path used as supporting texture inside the proof module."},
    "skip_proof": {"type": "boolean", "default": False, "description": "Skip the proof module in HTML share cards."},
    "dark_mode": {"type": "boolean", "default": False, "description": "Use dark background variant for HTML share cards."},
    "design_variance": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5, "description": "Design variance dial (1-10). Low (1-3): clean centered grid. Mid (4-7): editorial asymmetry. High (8-10): strong asymmetry with massive whitespace."},
    "layout_spec": {
        "type": "object",
        "description": "Optional layout specification overrides. When omitted, defaults are computed from material_type + design_variance.",
        "properties": {
            "columns": {"type": "integer", "minimum": 1, "maximum": 2},
            "alignment": {"type": "string", "enum": ["left", "center"]},
            "proof_position": {"type": "string", "enum": ["below", "right", "bottom"]},
            "accent_style": {"type": "string", "enum": ["left-strip", "top-bar", "none"]},
            "headline_size": {"type": "string", "enum": ["xl", "lg", "md", "sm"]},
            "padding": {"type": "string", "enum": ["tight", "normal", "generous"]},
            "proof_style": {"type": "string", "enum": ["card", "inline", "minimal"]},
        },
    },
    "set_scope": {"type": "boolean", "default": False, "description": "Route as a set orchestration brief, even though generation remains single-material"},
    "preserve": {"type": "array", "items": {"type": "string"}, "description": "Things that must stay fixed; repeat as needed"},
    "push": {"type": "array", "items": {"type": "string"}, "description": "Things that can be pushed or explored; repeat as needed"},
    "ban": {"type": "array", "items": {"type": "string"}, "description": "Things that must not appear; repeat as needed"},
    "pick": {"type": "array", "items": {"type": "string"}, "description": "Explicit role picks in the form role=source-key-or-path; repeat as needed"},
"max_iterations": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1, "description": "Max generate-critique-refine loops (1-3)"},
    "max_retries": {"type": "integer", "minimum": 0, "maximum": 2, "default": 1, "description": "Max quality-gate retries on very low scores (0-2)"},
    "internal_vlm_critique": {"type": "boolean", "default": False, "description": "Opt into the legacy internal VLM critique/refine loop after generation."},
    "skip_vlm": {"type": "boolean", "default": False, "description": "Deprecated compatibility flag. Internal VLM critique is off by default unless internal_vlm_critique is true."},
    "skip_route": {"type": "boolean", "default": False, "description": "Skip the routing stage and start at plan-draft"},
    "critique_mode": {"type": "string", "enum": ["advisory", "strict"], "default": "strict", "description": "How blocking critique findings should be treated inside pipeline orchestration"},
    "allow_blocking": {"type": "boolean", "default": False, "description": "Record an explicit bypass and continue even if critique or scratchpad blocking issues remain"},
    "source_version": {"type": "string", "description": "Version ID to iterate from (e.g. v012); establishes branch lineage."},
    "route": {"type": "string", "description": "Override the automatic route selection (e.g. reference_translate, generative_explore)."},
    "profile": {"type": "string", "description": "Optional brand-profile.json path"},
    "identity": {"type": "string", "description": "Optional brand-identity.json path"},
}

PIPELINE_MCP_REQUIRED = ["material_type"]


def _optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [value]
    out: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _bool(value: Any, default: bool = False) -> bool:
    return default if value is None else bool(value)


def _bounded_int(value: Any, *, default: int = 1, low: int = 1, high: int = 3) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, low), high)


def _pipeline_mode(value: Any, *, default: str = "hybrid") -> str:
    text = str(value or "").strip().lower()
    return text if text in {"reference", "inspiration", "hybrid"} else default


def _critique_mode(value: Any, *, default: str = "strict") -> str:
    return "advisory" if str(value or default).strip().lower() == "advisory" else "strict"


@dataclass
class PipelineRequest:
    material_type: str | None = None
    render_backend: str = "native"
    mode: str = "hybrid"
    tag: str | None = None
    prompt_seed: str | None = None
    mechanic: str | None = None
    purpose: str | None = None
    target_surface: str | None = None
    product_truth_expression: str | None = None
    abstraction_level: str | None = None
    goal: str | None = None
    briefing: str | None = None
    audience: str | None = None
    request: str | None = None
    motion_reference: str | None = None
    base_image: str | None = None
    source_url: str | None = None
    entity_type: str | None = None
    headline: str | None = None
    subhead: str | None = None
    cta: str | None = None
    proof_title: str | None = None
    proof_excerpt: str | None = None
    proof_row: str | None = None
    proof_meta: list[str] = field(default_factory=list)
    proof_crop_path: str | None = None
    skip_proof: bool = False
    dark_mode: bool = False
    design_variance: int = 5
    layout_spec: dict[str, Any] | None = None
    set_scope: bool = False
    preserve: list[str] = field(default_factory=list)
    push: list[str] = field(default_factory=list)
    ban: list[str] = field(default_factory=list)
    pick: list[str] = field(default_factory=list)
    max_iterations: int = 1
    max_retries: int = 1
    skip_vlm: bool = False
    internal_vlm_critique: bool = False
    skip_route: bool = False
    critique_mode: str = "strict"
    allow_blocking: bool = False
    source_version: str | None = None
    route: str | None = None
    profile: str | None = None
    identity: str | None = None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "PipelineRequest":
        return cls.from_mapping(vars(args))

    @classmethod
    def from_cli_args(cls, args: argparse.Namespace) -> "PipelineRequest":
        return cls.from_namespace(args)

    @classmethod
    def from_mcp_args(cls, args: Mapping[str, Any]) -> "PipelineRequest":
        return cls.from_mapping(args)

    @classmethod
    def from_args(cls, args: Mapping[str, Any]) -> "PipelineRequest":
        return cls.from_mcp_args(args)

    @classmethod
    def from_mapping(cls, args: Mapping[str, Any]) -> "PipelineRequest":
        return cls(
            material_type=_optional_str(args.get("material_type")),
            render_backend=("html" if str(args.get("render_backend") or "").strip().lower() == "html" else "native"),
            mode=_pipeline_mode(args.get("mode")),
            tag=_optional_str(args.get("tag")),
            prompt_seed=_optional_str(args.get("prompt_seed")),
            mechanic=_optional_str(args.get("mechanic")),
            purpose=_optional_str(args.get("purpose")),
            target_surface=_optional_str(args.get("target_surface")),
            product_truth_expression=_optional_str(args.get("product_truth_expression")),
            abstraction_level=_optional_str(args.get("abstraction_level")),
            goal=_optional_str(args.get("goal")),
            briefing=_optional_str(args.get("briefing")),
            audience=_optional_str(args.get("audience")),
            request=_optional_str(args.get("request")),
            motion_reference=_optional_str(args.get("motion_reference")),
            base_image=_optional_str(args.get("base_image")),
            source_url=_optional_str(args.get("source_url")),
            entity_type=_optional_str(args.get("entity_type")),
            headline=_optional_str(args.get("headline")),
            subhead=_optional_str(args.get("subhead")),
            cta=_optional_str(args.get("cta")),
            proof_title=_optional_str(args.get("proof_title")),
            proof_excerpt=_optional_str(args.get("proof_excerpt")),
            proof_row=_optional_str(args.get("proof_row")),
            proof_meta=_string_list(args.get("proof_meta")),
            proof_crop_path=_optional_str(args.get("proof_crop_path")),
            skip_proof=_bool(args.get("skip_proof"), False),
            dark_mode=_bool(args.get("dark_mode"), False),
            design_variance=_bounded_int(args.get("design_variance"), default=5, low=1, high=10),
            layout_spec=args.get("layout_spec") if isinstance(args.get("layout_spec"), dict) else None,
            set_scope=_bool(args.get("set_scope"), False),
            preserve=_string_list(args.get("preserve")),
            push=_string_list(args.get("push")),
            ban=_string_list(args.get("ban")),
            pick=_string_list(args.get("pick")),
            max_iterations=_bounded_int(args.get("max_iterations"), default=1, low=1, high=3),
            max_retries=_bounded_int(args.get("max_retries"), default=1, low=0, high=2),
            skip_vlm=_bool(args.get("skip_vlm"), False),
            internal_vlm_critique=_bool(args.get("internal_vlm_critique"), False),
            skip_route=_bool(args.get("skip_route"), False),
            critique_mode=_critique_mode(args.get("critique_mode"), default="strict"),
            allow_blocking=_bool(args.get("allow_blocking"), False),
            source_version=_optional_str(args.get("source_version")),
            route=_optional_str(args.get("route")),
            profile=_optional_str(args.get("profile")),
            identity=_optional_str(args.get("identity")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_namespace(self) -> argparse.Namespace:
        return argparse.Namespace(**self.with_pipeline_defaults().to_dict())

    def with_pipeline_defaults(self) -> "PipelineRequest":
        render_backend = str(self.render_backend or "").strip().lower()
        material_type = str(self.material_type or "").strip().lower()
        entity_type = str(self.entity_type or "").strip().lower()
        source_url = str(self.source_url or "").strip()
        if render_backend != "html" or not source_url:
            return self

        if not self.product_truth_expression:
            if entity_type in {"prompt", "skill", "library"}:
                self.product_truth_expression = f"real {entity_type} text resolved from source"
            else:
                self.product_truth_expression = "real source-derived product text"

        if not self.target_surface:
            self.target_surface = {
                "announcement-card": "portrait social poster / story-style share",
                "social": "square social feed share",
                "x-feed": "wide feed preview card",
            }.get(material_type, "social share card")

        if not self.purpose:
            base = {
                "prompt": "share a governed prompt as a branded social card",
                "skill": "share a governed skill as a branded social card",
                "library": "share a governed library as a branded social card",
            }.get(entity_type, "share a governed artifact as a branded social card")
            if material_type == "announcement-card":
                base = base.replace("social card", "portrait poster card")
            self.purpose = base

        return self

    def runner_kwargs(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_retries": self.max_retries,
            "skip_vlm": self.skip_vlm,
            "use_internal_vlm_critique": self.internal_vlm_critique,
            "skip_route": self.skip_route,
            "critique_mode": self.critique_mode,
            "allow_blocking": self.allow_blocking,
            "source_version": self.source_version,
            "route_override": self.route,
        }

    @staticmethod
    def build_critique_namespace(
        plan_path: str,
        *,
        critique_mode: str = "strict",
        allow_blocking: bool = False,
        base_image: str | None = None,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            plan=plan_path,
            prompt=None,
            material_type=None,
            render_backend="native",
            generation_mode="auto",
            mode="auto",
            model=None,
            aspect_ratio=None,
            resolution=None,
            duration=None,
            tag=None,
            image=None,
            reference_dir=None,
            motion_reference=None,
            motion_mode=None,
            character_orientation=None,
            keep_original_sound=False,
            preset=None,
            negative_prompt=None,
            style=None,
            make_gif=False,
            base_image=_optional_str(base_image),
            profile=None,
            identity=None,
            disable_brand_guardrails=False,
            allow_blocking=allow_blocking,
            output=None,
            format="json",
            critique_mode=_critique_mode(critique_mode),
        )

    @staticmethod
    def build_scratchpad_namespace(
        plan_path: str,
        plan: Mapping[str, Any],
        *,
        critique_mode: str = "strict",
        allow_blocking: bool = False,
        source_version: str | None = None,
        base_image: str | None = None,
        tag: str | None = None,
        render_backend: str = "native",
        source_url: str | None = None,
        entity_type: str | None = None,
        headline: str | None = None,
        subhead: str | None = None,
        cta: str | None = None,
        proof_title: str | None = None,
        proof_excerpt: str | None = None,
        proof_row: str | None = None,
        proof_meta: list[str] | None = None,
        proof_crop_path: str | None = None,
        skip_proof: bool = False,
        dark_mode: bool = False,
        design_variance: int = 5,
        layout_spec: dict[str, Any] | None = None,
        branch_id: str = "",
        parent_branch_id: str = "",
    ) -> argparse.Namespace:
        return argparse.Namespace(
            prompt=None,
            plan=plan_path,
            material_type=plan.get("material_type"),
            render_backend=("html" if str(render_backend or "").strip().lower() == "html" else "native"),
            generation_mode="auto",
            mode="auto",
            model=None,
            aspect_ratio=None,
            resolution=None,
            duration=None,
            tag=_optional_str(tag) or _optional_str(plan.get("tag")),
            source_url=_optional_str(source_url),
            entity_type=_optional_str(entity_type),
            headline=_optional_str(headline),
            subhead=_optional_str(subhead),
            cta=_optional_str(cta),
            proof_title=_optional_str(proof_title),
            proof_excerpt=_optional_str(proof_excerpt),
            proof_row=_optional_str(proof_row),
            proof_meta=_string_list(proof_meta),
            proof_crop_path=_optional_str(proof_crop_path),
            skip_proof=_bool(skip_proof, False),
            dark_mode=_bool(dark_mode, False),
            design_variance=_bounded_int(design_variance, default=5, low=1, high=10),
            layout_spec=layout_spec,
            image=None,
            reference_dir=None,
            motion_reference=None,
            motion_mode=None,
            character_orientation=None,
            keep_original_sound=False,
            preset=None,
            negative_prompt=None,
            style=None,
            make_gif=False,
            base_image=_optional_str(base_image),
            profile=None,
            identity=None,
            disable_brand_guardrails=False,
            skip_extraction=False,
            refresh_reference_analysis=False,
            allow_blocking=allow_blocking,
            output=None,
            format="json",
            critique_mode=_critique_mode(critique_mode),
            source_version=_optional_str(source_version),
            branch_id=branch_id,
            parent_branch_id=parent_branch_id,
        )

    @classmethod
    def mcp_input_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {key: dict(value) for key, value in PIPELINE_MCP_PROPERTIES.items()},
            "required": list(PIPELINE_MCP_REQUIRED),
        }


__all__ = [
    "PIPELINE_MCP_PROPERTIES",
    "PIPELINE_MCP_REQUIRED",
    "PipelineRequest",
]
