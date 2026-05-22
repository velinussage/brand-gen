"""Material plan creation, route classification, and plan critique.

Orchestrates the full material plan lifecycle — from parsing CLI picks
through role selection, mechanic synthesis, and plan assembly.  Also
handles route classification, plan critique payloads, identity freshness
checks, and improvement question generation.

Key functions:
    create_material_plan            — assemble a full material plan dict
    build_material_plan_from_args   — CLI-args wrapper around create_material_plan
    build_route_payload             — route classification payload
    build_plan_critique_payload     — critique a plan before generation
    check_identity_freshness        — check if identity needs a rebuild
    build_improvement_questions     — contextual agent questions
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .blackboard import (
    build_blackboard_feedback_directives,
    build_blackboard_learning_context,
    get_blackboard_learning_warnings,
)
from .card_engine import ALLOWED_HTML_MATERIALS
from .brand_policy import (
    load_inspiration_prompt_context,
    normalize_material_brand_policy,
    summarize_identity,
)
from .critique_policy import build_critique_policy
from .custom_scratchpad import html_share_card_block_reason
from .inspiration_board import persist_inspiration_source_selection, persist_plan_inspiration_board
from .learnings_memory import load_learnings_memory
from .aesthetic_archetypes import list_archetypes, pick_rotating_archetype
from .aesthetic_curation import build_aesthetic_direction_brief, select_aesthetic_capsule
from .material_prompt_profiles import get_material_prompt_profile
from .product_truth import (
    build_product_truth_metadata,
    render_product_truth_contract,
    validate_product_truth_plan,
)
from .plan_validation import (
    detect_deterministic_text_surface_request,
    normalize_aesthetic_commitment,
    normalize_complexity_tier,
    normalize_visual_density,
    validate_material_plan_dict,
)
from .pipeline_types import AestheticExperiment, VariantSpec
from .reference_role_packs import (
    build_inspiration_translation_summary,
    build_selected_role_translation,
    evaluate_reference_quality,
    evaluate_reference_role_assignments,
    resolve_explicit_inspiration_selection,
    select_inspiration_sources,
    source_risk_rank,
    stable_mechanic_id,
    suggest_reference_role_pack,
)
from .request_intent import (
    infer_illustration_only_request,
    illustration_only_hits,
    resolve_planner_material_type,
)
from .runtime import *
from .runtime_brand import load_alignment_questions, load_idea_tracks, load_pipeline_config, load_prompt_fragments
from .surface_strategy import recommend_surface_strategies

__all__ = [
    # Plan creation
    "parse_role_pick",
    "build_plan_prompt_seed",
    "synthesize_system_mechanic",
    "create_material_plan",
    "build_material_plan_from_args",
    # Idea tracks and alignment
    "default_idea_tracks",
    "default_alignment_questions",
    # Route classification
    "build_route_payload",
    "classify_workflow_route_smart",
    "build_route_candidates",
    "preferred_material_engine",
    # Plan critique
    "build_plan_critique_payload",
    # Identity and improvement
    "check_identity_freshness",
    "build_improvement_questions",
    # Plan loading
    "select_plan_roles",
    "extract_plan_payload",
    "load_plan_payload",
]


def parse_role_pick(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError(f"Invalid --pick '{value}'. Expected role=source-key-or-path.")
    role, picked = value.split("=", 1)
    role = role.strip().lower()
    picked = picked.strip()
    if role not in ROLE_PACK_TAG_PRIORITY:
        raise ValueError(f"Invalid role '{role}'. Expected one of: {', '.join(ROLE_PACK_TAG_PRIORITY)}")
    if not picked:
        raise ValueError("Pick value cannot be empty.")
    return role, picked


def build_plan_prompt_seed(
    identity: dict,
    material_type: str,
    workflow_mode: str,
    system_mechanic: str,
    preserve: list[str],
    push: list[str],
    ban: list[str],
    purpose: str = "",
    target_surface: str = "",
    product_truth_expression: str = "",
    brand_anchor_rule: str = "",
    briefing: str = "",
) -> str:
    def join_items(items: list[str]) -> str:
        items = [str(item).strip() for item in items if str(item).strip()]
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            return f"{items[0]} and {items[1]}"
        return f"{', '.join(items[:-1])}, and {items[-1]}"

    brand_name = (identity.get("brand") or {}).get("name") or "the brand"
    preserve_text = join_items(preserve) or "exact mark recognition, palette discipline, and approved brand primitives"
    push_text = join_items(push) or "composition authority, layout confidence, and one sharper system expression"
    ban_text = join_items(ban) or "generic startup symbols, invented copy, and unrelated decorative tricks"
    mechanic = system_mechanic.strip() or "one clear repeated system mechanic"
    framing_bits = []
    if purpose:
        framing_bits.append(f"Purpose: {purpose}")
    if target_surface:
        framing_bits.append(f"Surface: {target_surface}")
    if product_truth_expression:
        framing_bits.append(f"Product truth: {product_truth_expression}")
    if brand_anchor_rule:
        framing_bits.append(f"Branding rule: {brand_anchor_rule}")
    if briefing:
        framing_bits.append(f"Creative brief: {briefing}")
    return (
        f"Create a {material_type} for {brand_name} in {workflow_mode} mode. "
        f"Use {mechanic} as the one system mechanic. "
        f"{' '.join(framing_bits)} "
        f"Preserve {preserve_text}. "
        f"Push {push_text}. "
        f"Ban {ban_text}. "
        f"Keep the output brand-led, concrete, and specific rather than abstract."
    )


def synthesize_system_mechanic(
    material_type: str,
    *,
    purpose: str = "",
    target_surface: str = "",
    product_truth_expression: str = "",
    selected_mechanic_labels: list[str] | None = None,
) -> str:
    material_label = str(material_type or "material").replace("-", " ").strip() or "material"
    product_truth = str(product_truth_expression or "").strip()
    surface = str(target_surface or "").strip()
    purpose_text = str(purpose or "").strip()
    mechanics = [str(item).strip() for item in (selected_mechanic_labels or []) if str(item).strip()]
    primary_mechanic = mechanics[0] if mechanics else ""

    if product_truth and primary_mechanic:
        return f"one {material_label} composition built around {product_truth} with {primary_mechanic}"
    if product_truth:
        return f"one {material_label} composition built around {product_truth}"
    if primary_mechanic:
        return f"one {material_label} composition using {primary_mechanic}"
    if surface:
        return f"one clear {material_label} composition tailored for {surface}"
    if purpose_text:
        return f"one clear {material_label} composition that serves {purpose_text}"
    return f"one clear {material_label} system move"


def create_material_plan(
    *,
    brand_dir: Path,
    identity_path: Path,
    identity: dict,
    material_type: str,
    mode: str,
    mechanic: str,
    preserve: list[str],
    push: list[str],
    ban: list[str],
    picks: dict[str, str],
    prompt_seed: str | None = None,
    purpose: str | None = None,
    target_surface: str | None = None,
    product_truth_expression: str | None = None,
    abstraction_level: str | None = None,
    render_backend: str | None = None,
    source_url: str | None = None,
    entity_type: str | None = None,
    design_variance: int | None = None,
    complexity_tier: str | None = None,
    visual_density: int | str | None = None,
    aesthetic_commitment: str | None = None,
    aesthetic_capsule: str | None = None,
    style_handle: str | None = None,
    prompt_subject: str | None = None,
    prompt_style_descriptors: str | None = None,
    prompt_lighting: str | None = None,
    prompt_camera: str | None = None,
    prompt_composition: str | None = None,
    prompt_details: str | None = None,
    set_membership: dict | None = None,
    briefing: str | None = None,
    base_image: str | None = None,
    inspiration_picks: list[str] | None = None,
    accept_inspiration_recommendations: bool = False,
    branch_id: str | None = None,
    parent_branch_id: str | None = None,
) -> tuple[dict, list[str]]:
    requested_material_type = material_type
    material_type, material_type_resolution_note = resolve_planner_material_type(
        material_type,
        purpose=purpose or "",
        target_surface=target_surface or "",
        prompt_seed=prompt_seed or "",
        briefing=briefing or "",
        product_truth_expression=product_truth_expression or "",
    )

    candidates = suggest_reference_role_pack(brand_dir, material_type)
    configured_required_roles = list(candidates.get("required_roles") or [])
    candidate_counts = {
        role: len(candidates.get("candidates", {}).get(role) or [])
        for role in (candidates.get("priority") or ROLE_PACK_TAG_PRIORITY)
    }
    available_required_roles = [
        role for role in configured_required_roles
        if picks.get(role) or candidate_counts.get(role, 0) > 0
    ]
    unavailable_required_roles = [role for role in configured_required_roles if role not in available_required_roles]

    selected_roles, _raw_missing_required = select_plan_roles(candidates, picks)
    selected_roles = [dict(item, translation=build_selected_role_translation(item)) for item in selected_roles]
    reference_quality = evaluate_reference_quality(role_pack_material_key(material_type) or "", selected_roles)
    role_assignment_quality = evaluate_reference_role_assignments(role_pack_material_key(material_type) or "", selected_roles)
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        identity_path=identity_path,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
    )
    inspiration_context = load_inspiration_prompt_context(
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        material_type=material_type,
        brand_dir=brand_dir,
    )
    illustration_only = infer_illustration_only_request(
        purpose=purpose or "",
        target_surface=target_surface or "",
        prompt_seed=prompt_seed or "",
        briefing=briefing or "",
        preserve=preserve or [],
        push=push or [],
        ban=ban or [],
    )
    illustration_hits = illustration_only_hits(
        purpose=purpose or "",
        target_surface=target_surface or "",
        prompt_seed=prompt_seed or "",
        briefing=briefing or "",
        preserve=preserve or [],
        push=push or [],
        ban=ban or [],
    )
    inspiration_memory = inspiration_context.get("memory") or {}
    inspiration_recommendations = select_inspiration_sources(
        list(inspiration_context.get("source_records") or []),
        selected_roles=selected_roles,
        material_type=material_type,
    )
    inspiration_selection = resolve_explicit_inspiration_selection(
        list(inspiration_context.get("source_records") or []),
        picks=inspiration_picks,
        recommended_records=list(inspiration_recommendations.get("records") or []),
        accept_recommendations=accept_inspiration_recommendations,
    )
    selected_inspiration_sources = list(inspiration_selection.get("records") or [])

    selected_inspiration_translation_payload = build_selected_inspiration_translation(
        selected_inspiration_sources,
        material_type=material_type,
    )
    selected_mechanic_labels = list(selected_inspiration_translation_payload.get("mechanics") or [])
    if not selected_mechanic_labels:
        selected_mechanic_labels = list(inspiration_memory.get("composition_archetypes") or [])[:2]
    selected_mechanic_ids = dedupe_keep_order(
        [
            stable_mechanic_id(str(item.get("source_key") or item.get("source_name") or "source"), label)
            for item in selected_inspiration_sources
            for label in selected_mechanic_labels[:2]
        ]
    )[:6]
    relaxed_role_pack_gate = bool(
        not picks
        and selected_inspiration_sources
        and configured_required_roles
        and not available_required_roles
    )
    enforced_required_roles = [] if relaxed_role_pack_gate else available_required_roles
    selected_role_names = [str(item.get("role") or "").strip() for item in selected_roles if str(item.get("role") or "").strip()]
    missing_required = [role for role in enforced_required_roles if role not in selected_role_names]
    role_pack_requirement_mode = "advisory_inspiration_fallback" if relaxed_role_pack_gate else "strict"
    learning_context = build_blackboard_learning_context(brand_dir, material_type)
    feedback_directives = build_blackboard_feedback_directives(brand_dir, material_type)
    illustration_inspiration_required = bool(
        illustration_only
        or role_pack_material_key(material_type) in {
            "concept_illustration",
            "system_explainer_illustration",
            "editorial_metaphor_illustration",
            "brand_scene",
            "illustrated_brand_world",
        }
    )
    min_inspiration_sources = 3 if illustration_only else (2 if illustration_inspiration_required else 0)
    learned_setup_warnings = get_blackboard_learning_warnings(
        brand_dir,
        material_type,
        proposed_mode=mode,
        has_reference_roles=bool(selected_roles),
        source_version="",
        board=None,
    )
    learned_setup_warnings = dedupe_keep_order(
        list(learned_setup_warnings) + list(feedback_directives.get("warnings") or [])
    )
    policy = normalize_material_brand_policy(material_type, identity=identity)
    preserve = preserve or [policy.get("product_truth_expression") or "stored brand palette, mark recognition, and real product truth"]
    push = push or ["clear focal hierarchy and one stronger composition move"]
    ban = ban or ["generic off-brand decoration or invented product chrome"]
    if feedback_directives.get("push"):
        push = dedupe_keep_order(list(push or []) + list(feedback_directives["push"]))
    if feedback_directives.get("ban"):
        ban = dedupe_keep_order(list(ban or []) + list(feedback_directives["ban"]))
    if purpose:
        policy["purpose"] = purpose
    if target_surface:
        policy["target_surface"] = target_surface
    if product_truth_expression:
        policy["product_truth_expression"] = product_truth_expression
    if abstraction_level:
        policy["abstraction_level"] = abstraction_level
    # Brand-gen must not inject globally hard-coded product knowledge for any
    # one brand. Product truth now comes only from the active brand identity,
    # explicit user brief, selected references, and per-brand policy/memory.
    capability_focus = {
        "candidates": [],
        "selected": [],
        "directive": "",
        "avoid_repeating_linear_story": False,
    }
    resolved_render_backend = "html" if str(render_backend or "").strip().lower() == "html" else "native"
    resolved_entity_type = str(entity_type or "").strip().lower()
    resolved_source_url = str(source_url or "").strip()
    if resolved_render_backend == "html" and not resolved_entity_type and not resolved_source_url:
        resolved_entity_type = "artifact"
    resolved_design_variance = max(1, min(int(design_variance or 5), 10))
    resolved_complexity_tier = normalize_complexity_tier(complexity_tier, material_type=material_type)
    resolved_visual_density = normalize_visual_density(visual_density, material_type=material_type)
    if visual_density in (None, "") and feedback_directives.get("visual_density_cap"):
        resolved_visual_density = min(resolved_visual_density, int(feedback_directives["visual_density_cap"]))
    if not complexity_tier and feedback_directives.get("complexity_tier_hint"):
        hinted_tier = normalize_complexity_tier(str(feedback_directives["complexity_tier_hint"]), material_type=material_type)
        if hinted_tier:
            resolved_complexity_tier = hinted_tier
    resolved_aesthetic_commitment = normalize_aesthetic_commitment(aesthetic_commitment)
    material_prompt_profile = get_material_prompt_profile(material_type) or {}
    text_rendering_strategy = ""
    html_policy_block = (
        ""
        if resolved_render_backend == "html"
        else html_share_card_block_reason(brand_dir, material_type)
    )
    if (
        resolved_render_backend != "html"
        and not html_policy_block
        and material_type in ALLOWED_HTML_MATERIALS
        and detect_deterministic_text_surface_request(
            {
                "material_type": material_type,
                "prompt_seed": prompt_seed or briefing or "",
                "purpose": policy.get("purpose") or "",
                "target_surface": policy.get("target_surface") or "",
                "product_truth_expression": policy.get("product_truth_expression") or "",
                "preserve": preserve or [],
                "push": push or [],
                "ban": ban or [],
            },
            material_type=material_type,
        )
    ):
        resolved_render_backend = "html"
        text_rendering_strategy = "html"
    # Aesthetic archetype: rotate across the material's archetype library so
    # no single paradigm fossilizes (addresses v181/v182 "same mood prose"
    # defaults). Read rotation window from iteration memory.
    _archetype_memory = load_iteration_memory(brand_dir)
    _resolved_archetype = pick_rotating_archetype(material_type, _archetype_memory)
    _style_text = " ".join(
        str(item or "").strip()
        for item in [style_handle, prompt_style_descriptors, aesthetic_commitment, prompt_seed, purpose, target_surface, briefing]
        if str(item or "").strip()
    )
    _capsule_selection = select_aesthetic_capsule(
        brand_dir=brand_dir,
        material_type=material_type,
        requested_capsule=aesthetic_capsule,
        style_text=_style_text,
    )
    _resolved_capsule = _capsule_selection.get("capsule") if isinstance(_capsule_selection, dict) else None
    _aesthetic_direction_brief = build_aesthetic_direction_brief(
        brand_dir=brand_dir,
        material_type=material_type,
        style_text=_style_text,
        count=3,
    )
    strategy_context = recommend_surface_strategies(
        material_type=material_type,
        entity_type=resolved_entity_type,
        render_backend=resolved_render_backend,
        source_url=resolved_source_url,
        purpose=policy.get("purpose") or "",
        target_surface=policy.get("target_surface") or "",
        product_truth_expression=policy.get("product_truth_expression") or "",
        design_variance=resolved_design_variance,
        brand_dir=brand_dir,
        identity=identity,
    )
    resolved_mechanic = (mechanic or "").strip()
    mechanic_source = "explicit"
    if not resolved_mechanic:
        resolved_mechanic = synthesize_system_mechanic(
            material_type,
            purpose=policy.get("purpose") or "",
            target_surface=policy.get("target_surface") or "",
            product_truth_expression=policy.get("product_truth_expression") or "",
            selected_mechanic_labels=selected_mechanic_labels,
        )
        mechanic_source = "auto_synthesized"
    seed = prompt_seed or build_plan_prompt_seed(
        identity,
        material_type,
        mode,
        resolved_mechanic,
        preserve or [],
        push or [],
        ban or [],
        purpose=policy.get("purpose") or "",
        target_surface=policy.get("target_surface") or "",
        product_truth_expression=policy.get("product_truth_expression") or "",
        brand_anchor_rule=policy.get("rule") or "",
        briefing=briefing or "",
    )
    memory_seed_prompt = str(inspiration_memory.get("seed_prompt") or "").strip()
    if capability_focus.get("directive"):
        seed = f"{seed} {capability_focus['directive']}".strip()
    if not prompt_seed and memory_seed_prompt:
        seed = f"{seed} {memory_seed_prompt}".strip()
    variants: list[VariantSpec] = []
    selected_variant_index = 0
    selected_capsule_id = str((_resolved_capsule or {}).get("id") or "")
    archetype_id = str((_resolved_archetype or {}).get("id") or "")
    for idx, raw_variant in enumerate(_aesthetic_direction_brief.get("variants") or []):
        if not isinstance(raw_variant, dict):
            continue
        payload = {
            **raw_variant,
            "variant_id": raw_variant.get("variant_id") or raw_variant.get("capsule_id") or f"variant-{idx + 1}",
            "archetype": archetype_id,
            "design_variance": resolved_design_variance,
        }
        variant = VariantSpec.from_dict(payload)
        if selected_capsule_id and variant.capsule == selected_capsule_id:
            selected_variant_index = len(variants)
        variants.append(variant)
    if not variants and _resolved_capsule:
        variants.append(
            VariantSpec(
                variant_id=selected_capsule_id or "selected-capsule",
                label=str((_resolved_capsule or {}).get("label") or selected_capsule_id or "selected capsule"),
                archetype=archetype_id,
                capsule=selected_capsule_id,
                design_variance=resolved_design_variance,
                visual_thesis=str(((_resolved_capsule or {}).get("style_description") or {}).get("composition") or ""),
                payload=dict(_resolved_capsule or {}),
            )
        )
    if not variants:
        variants.append(
            VariantSpec(
                variant_id="default-direction",
                label="Default direction",
                archetype=archetype_id,
                capsule=selected_capsule_id,
                design_variance=resolved_design_variance,
                visual_thesis=seed[:160],
            )
        )
    experiment_branch_id = branch_id or AestheticExperiment.stable_branch_id(
        brand_key=brand_dir.name,
        material_type=material_type,
        seed=seed,
        iteration=1,
    )
    experiment = AestheticExperiment(
        branch_id=experiment_branch_id,
        parent_branch_id=parent_branch_id or "",
        archetype=archetype_id,
        capsule=selected_capsule_id,
        design_variance=resolved_design_variance,
        variants=variants,
        selected_variant_index=selected_variant_index,
        selection_rationale="; ".join(str(item) for item in ((_capsule_selection or {}).get("reasons") or [])[:3]),
    )
    _product_truth_plan = {
        "brand_dir": str(brand_dir),
        "material_type": material_type,
        "purpose": policy.get("purpose") or "",
        "target_surface": policy.get("target_surface") or "",
        "product_truth_expression": policy.get("product_truth_expression") or "",
        "prompt_seed": seed,
        "preserve": preserve or [],
        "push": push or [],
        "ban": ban or [],
    }
    product_truth_contract = render_product_truth_contract(_product_truth_plan, identity=identity)
    product_truth_metadata = build_product_truth_metadata(_product_truth_plan, identity=identity)
    product_truth_validation = validate_product_truth_plan(_product_truth_plan, identity=identity)

    plan = {
        "version": 2,
        "brand_dir": str(brand_dir),
        "identity_path": str(identity_path),
        "material_type": material_type,
        "requested_material_type": requested_material_type,
        "material_type_resolution": {
            "requested": requested_material_type,
            "resolved": material_type,
            "changed": requested_material_type != material_type,
            "note": material_type_resolution_note,
        },
        "mode": mode,
        "render_backend": resolved_render_backend,
        "text_rendering_strategy": text_rendering_strategy,
        "source_url": resolved_source_url,
        "entity_type": resolved_entity_type,
        "purpose": policy.get("purpose") or "",
        "target_surface": policy.get("target_surface") or "",
        "product_truth_expression": policy.get("product_truth_expression") or "",
        "source_shape": strategy_context.get("source_shape") or "",
        "exact_text_required": bool(strategy_context.get("exact_text_required")),
        "selected_surface_strategy": strategy_context.get("selected_surface_strategy") or "",
        "selected_surface_strategy_label": strategy_context.get("selected_surface_strategy_label") or "",
        "selected_surface_strategy_summary": strategy_context.get("selected_surface_strategy_summary") or "",
        "selected_surface_strategy_layout_family": strategy_context.get("selected_surface_strategy_layout_family") or "",
        "selected_surface_strategy_prompt_directive": strategy_context.get("selected_surface_strategy_prompt_directive") or "",
        "surface_strategy_reason": strategy_context.get("surface_strategy_reason") or "",
        "surface_strategy_candidates": list(strategy_context.get("surface_strategy_candidates") or []),
        "abstraction_level": policy.get("abstraction_level") or "",
        "design_variance": resolved_design_variance,
        "complexity_tier": resolved_complexity_tier,
        "visual_density": resolved_visual_density,
        "material_prompt_profile": material_prompt_profile,
        "product_truth_contract": product_truth_contract,
        "product_truth_metadata": product_truth_metadata,
        "product_truth_validation": product_truth_validation,
        "aesthetic_commitment": resolved_aesthetic_commitment or "",
        "aesthetic_capsule": _resolved_capsule or None,
        "aesthetic_capsule_id": (_resolved_capsule or {}).get("id") or "",
        "aesthetic_capsule_selection": {
            "source": (_capsule_selection or {}).get("source") or "none",
            "score": (_capsule_selection or {}).get("score") or 0,
            "reasons": list((_capsule_selection or {}).get("reasons") or []),
            "warnings": list((_capsule_selection or {}).get("warnings") or []),
        },
        "aesthetic_direction_brief": _aesthetic_direction_brief,
        "aesthetic_style_strength": (_resolved_capsule or {}).get("style_strength_default"),
        "aesthetic_reference_roles": dict(((_resolved_capsule or {}).get("reference_roles") or {})),
        "aesthetic_archetype": _resolved_archetype or None,
        "aesthetic_archetype_id": (_resolved_archetype or {}).get("id") or "",
        "branch_id": experiment.branch_id,
        "parent_branch_id": experiment.parent_branch_id,
        "selected_direction_id": experiment.variants[experiment.selected_variant_index].variant_id,
        "experiment": experiment.to_dict(),
        "prompt_subject": (prompt_subject or "").strip(),
        "prompt_style_descriptors": (prompt_style_descriptors or "").strip(),
        "prompt_lighting": (prompt_lighting or "").strip(),
        "prompt_camera": (prompt_camera or "").strip(),
        "prompt_composition": (prompt_composition or "").strip(),
        "prompt_details": (prompt_details or "").strip(),
        "briefing": briefing or "",
        "base_image": str(base_image or "").strip(),
        "brand_anchor_policy": policy,
        "system_mechanic": resolved_mechanic,
        "system_mechanic_source": mechanic_source,
        "preserve": preserve or [],
        "push": push or [],
        "ban": ban or [],
        "artifact_scope": "illustration_only" if illustration_only else "full_surface",
        "request_signals": {
            "illustration_only": illustration_only,
            "illustration_only_hits": illustration_hits,
        },
        "capability_focus": capability_focus,
        "selected_inspiration_ids": [],
        "inspiration_recommendations": {
            "mode": inspiration_recommendations.get("mode") or "advisory_shortlist",
            "reason": inspiration_recommendations.get("reason") or "",
            "recommended_sources": list(inspiration_recommendations.get("records") or []),
        },
        "selected_inspiration_source_keys": [
            str(item.get("source_key") or item.get("source_name") or "").strip()
            for item in selected_inspiration_sources
            if str(item.get("source_key") or item.get("source_name") or "").strip()
        ],
        "selected_inspiration_sources": selected_inspiration_sources,
        "selected_mechanic_ids": selected_mechanic_ids,
        "selected_mechanic_labels": selected_mechanic_labels,
        "selected_inspiration_translation": selected_inspiration_translation_payload.get("translation") or "",
        "inspiration_selection_reason": inspiration_selection.get("reason") or "",
        "inspiration_selection_mode": inspiration_selection.get("mode") or "unselected",
        "inspiration_requirements": {
            "required": illustration_inspiration_required,
            "min_selected_sources": min_inspiration_sources,
            "reason": (
                "Standalone or non-interface illustration work needs an explicit inspiration set so the pipeline does not fall back to page chrome, posters, or generic diagrams."
                if illustration_inspiration_required
                else ""
            ),
        },
        "inspiration_memory_summary": str(inspiration_memory.get("summary") or ""),
        "inspiration_memory_seed_prompt": memory_seed_prompt,
        "learning_context": learning_context,
        "feedback_directives": feedback_directives,
        "learned_setup_warnings": learned_setup_warnings,
        "prompt_seed": seed,
        "inspiration_translation": build_inspiration_translation_summary(selected_roles),
        "role_pack": {
            "material_key": candidates.get("material_key"),
            "priority": candidates.get("priority") or [],
            "required_roles": enforced_required_roles,
            "configured_required_roles": configured_required_roles,
            "unavailable_required_roles": unavailable_required_roles,
            "requirement_mode": role_pack_requirement_mode,
            "prefer_unique_sources": candidates.get("prefer_unique_sources", True),
            "selection_note": candidates.get("selection_note") or "",
            "selected_roles": selected_roles,
            "missing_required_roles": missing_required,
            "quality_errors": reference_quality.get("errors") or [],
            "quality_warnings": reference_quality.get("warnings") or [],
            "role_assignment_warnings": role_assignment_quality.get("warnings") or [],
        },
    }
    if set_membership:
        plan["set_membership"] = set_membership
    return plan, missing_required


def build_material_plan_from_args(args, brand_dir: Path) -> tuple[Path, dict, list[str]]:
    _, identity_path, _, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    picks: dict[str, str] = {}
    for raw in getattr(args, "pick", None) or []:
        role, value = parse_role_pick(raw)
        picks[role] = value
    plan, missing_required = create_material_plan(
        brand_dir=brand_dir,
        identity_path=identity_path,
        identity=identity,
        material_type=args.material_type,
        mode=args.mode,
        mechanic=args.mechanic or "",
        preserve=getattr(args, "preserve", None) or [],
        push=getattr(args, "push", None) or [],
        ban=getattr(args, "ban", None) or [],
        picks=picks,
        prompt_seed=getattr(args, "prompt_seed", None),
        purpose=getattr(args, "purpose", None),
        target_surface=getattr(args, "target_surface", None),
        product_truth_expression=getattr(args, "product_truth_expression", None),
        abstraction_level=getattr(args, "abstraction_level", None),
        render_backend=getattr(args, "render_backend", None),
        source_url=getattr(args, "source_url", None),
        entity_type=getattr(args, "entity_type", None),
        design_variance=getattr(args, "design_variance", None),
        complexity_tier=getattr(args, "complexity_tier", None),
        visual_density=getattr(args, "visual_density", None),
        aesthetic_commitment=getattr(args, "aesthetic_commitment", None),
        prompt_subject=getattr(args, "prompt_subject", None),
        aesthetic_capsule=getattr(args, "aesthetic_capsule", None),
        style_handle=getattr(args, "style_handle", None),
        prompt_style_descriptors=getattr(args, "prompt_style_descriptors", None),
        prompt_lighting=getattr(args, "prompt_lighting", None),
        prompt_camera=getattr(args, "prompt_camera", None),
        prompt_composition=getattr(args, "prompt_composition", None),
        prompt_details=getattr(args, "prompt_details", None),
        briefing=getattr(args, "briefing", None),
        base_image=getattr(args, "base_image", None),
        branch_id=getattr(args, "branch_id", None),
        parent_branch_id=getattr(args, "parent_branch_id", None),
        accept_inspiration_recommendations=True,
    )
    workflow_id = resolve_workflow_id(plan)
    plan["workflow_id"] = workflow_id
    selection = persist_plan_inspiration_board(brand_dir, plan, workflow_id=workflow_id)
    source_ids, board_path = persist_inspiration_source_selection(
        brand_dir,
        list(plan.get("selected_inspiration_sources") or []),
        workflow_id=workflow_id,
        direction_id=selection.get("direction_id"),
    )
    plan["selected_inspiration_ids"] = source_ids
    plan["inspiration_board"] = {
        **dict(plan.get("inspiration_board") or {}),
        "board_path": board_path or ((plan.get("inspiration_board") or {}).get("board_path") or ""),
        "selected_inspiration_ids": source_ids,
    }
    return identity_path, plan, missing_required


def default_idea_tracks(material_type: str) -> list[dict]:
    normalized = (material_type or "").strip().lower().replace("-", "_")
    data = load_idea_tracks()
    tracks = data.get("tracks", {})
    key = normalized if normalized in tracks else (role_pack_material_key(material_type) or normalized)
    default_track = data.get("default_track", {
        "name": "core brand extension",
        "mechanic": "one clear repeated brand mechanic",
        "why": "Best when you need a safe starting direction before branching.",
        "preserve": ["brand truth", "palette", "mark recognition"],
        "push": ["one composition move", "one system mechanic", "one application idea"],
        "ban": ["generic startup aesthetics", "invented text", "unrelated symbols"],
    })
    return tracks.get(key, [default_track])


def default_alignment_questions(material_type: str) -> list[str]:
    normalized = (material_type or "").strip().lower().replace("-", "_")
    data = load_alignment_questions()
    material_specific = data.get("material_specific", {})
    key = normalized if normalized in material_specific else (role_pack_material_key(material_type) or normalized)
    common = data.get("common", [
        "Which direction feels most like the brand you want to become, not just the brand you have now?",
        "Should this feel calmer and more institutional, or bolder and more collectible?",
        "What would make you reject a version immediately?",
    ])
    return common + material_specific.get(key, [])


def build_route_payload(args, brand_dir: Path, profile: dict, identity: dict) -> dict:
    route_override = getattr(args, "route", None)

    # Agent-provided route override — skip all scoring
    if route_override:
        route_info = classify_workflow_route_smart(
            getattr(args, "material_type", None),
            route_override=route_override,
        )
    else:
        try:
            try:
                from .route_predicates import RoutingBrief, route_brief
            except ImportError:  # pragma: no cover - top-level compatibility
                from route_predicates import RoutingBrief, route_brief  # type: ignore

            route_info = route_brief(
                RoutingBrief(
                    material_type=getattr(args, "material_type", None),
                    material_key=role_pack_material_key(getattr(args, "material_type", None)),
                    goal=getattr(args, "goal", "") or "",
                    request=getattr(args, "request", "") or "",
                    render_backend=getattr(args, "render_backend", "") or "native",
                    source_url=getattr(args, "source_url", "") or "",
                    entity_type=getattr(args, "entity_type", "") or "",
                    has_motion_reference=bool(getattr(args, "motion_reference", None)),
                    set_scope=bool(getattr(args, "set_scope", False)),
                    reference_image_count=0,
                    mode=getattr(args, "mode", None),
                )
            )
        except Exception:
            route_info = classify_workflow_route_smart(
                getattr(args, "material_type", None),
                goal=getattr(args, "goal", "") or "",
                request=getattr(args, "request", "") or "",
                has_motion_reference=bool(getattr(args, "motion_reference", None)),
                set_scope=bool(getattr(args, "set_scope", False)),
            )
    route = route_info["route"]
    illustration_only = infer_illustration_only_request(
        goal=getattr(args, "goal", "") or "",
        request=getattr(args, "request", "") or "",
    )
    plan_needed = route_info["route_key"] in {"reference_translate", "generative_explore", "motion_specialist"}
    result = {
        "schema_type": "workflow_route",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "material_type": getattr(args, "material_type", None) or "",
        "goal": getattr(args, "goal", "") or "",
        "request": getattr(args, "request", "") or "",
        "route_key": route_info["route_key"],
        "route_label": route.get("label") or route_info["route_key"],
        "specialists": route.get("specialists") or [],
        "required_assets": route.get("required_assets") or [],
        "required_questions": route.get("required_questions") or [],
        "next_commands": route.get("next_commands") or [],
        "notes": route.get("notes") or "",
        "should_plan_first": plan_needed,
        "should_compose_deterministically": False,
        "llm_routed": route_info.get("llm_routed", False),
        "score": route_info.get("score", 0.0),
        "method": route_info.get("method", "default"),
        "score_vector": route_info.get("score_vector", {}),
        "brand_dir": str(brand_dir),
        "brand_dna": summarize_identity(profile, identity),
        "request_signals": {
            "illustration_only": illustration_only,
            "illustration_only_hits": illustration_only_hits(
                goal=getattr(args, "goal", "") or "",
                request=getattr(args, "request", "") or "",
            ),
        },
    }
    # Include route candidates so the calling agent can override if the
    # default route doesn't match intent.  Re-run with --route <key>.
    if illustration_only and role_pack_material_key(getattr(args, "material_type", None)) in {"browser_illustration", "feature_illustration", "landing_hero", "product_banner", "terminal_hero", "command_illustration"}:
        result.setdefault("warnings", []).append(
            "Illustration-only intent conflicts with an interface/page-adjacent material type. For static hero sidecar art, prefer website-hero-illustration or another standalone illustration material. Use landing-hero when the desired output is the deployable hero background/sidecar animation, not a full page/UI mockup."
        )
    if route_info.get("method") != "agent_override":
        result["route_candidates"] = build_route_candidates(
            getattr(args, "material_type", None),
            goal=getattr(args, "goal", "") or "",
            request=getattr(args, "request", "") or "",
        )
    return result


def build_plan_critique_payload(
    args,
    *,
    brand_dir: Path,
    wrapper: dict,
    plan: dict,
    critique_mode: str = "advisory",
    entrypoint: str = "critique-plan",
    allow_blocking: bool = False,
) -> dict:
    effective_plan = dict(plan)
    cli_base_image = str(getattr(args, "base_image", None) or "").strip()
    if cli_base_image and not str(effective_plan.get("base_image") or "").strip():
        effective_plan["base_image"] = cli_base_image
    report = validate_material_plan_dict(effective_plan)
    preview_args = argparse.Namespace(
        prompt=getattr(args, "prompt", None),
        plan=str(Path(args.plan).expanduser().resolve()) if getattr(args, "plan", None) else "",
        material_type=getattr(args, "material_type", None),
        render_backend=effective_plan.get("render_backend") or getattr(args, "render_backend", "native"),
        generation_mode=getattr(args, "generation_mode", "auto"),
        mode=getattr(args, "mode", "auto"),
        model=getattr(args, "model", None),
        aspect_ratio=getattr(args, "aspect_ratio", None),
        resolution=getattr(args, "resolution", None),
        duration=getattr(args, "duration", None),
        tag=getattr(args, "tag", None),
        source_url=effective_plan.get("source_url") or getattr(args, "source_url", None),
        entity_type=effective_plan.get("entity_type") or getattr(args, "entity_type", None),
        image=getattr(args, "image", None),
        reference_dir=getattr(args, "reference_dir", None),
        motion_reference=getattr(args, "motion_reference", None),
        motion_mode=getattr(args, "motion_mode", None),
        character_orientation=getattr(args, "character_orientation", None),
        keep_original_sound=getattr(args, "keep_original_sound", False),
        preset=getattr(args, "preset", None),
        negative_prompt=getattr(args, "negative_prompt", None),
        style=getattr(args, "style", None),
        make_gif=getattr(args, "make_gif", False),
        base_image=getattr(args, "base_image", None),
        profile=getattr(args, "profile", None),
        identity=getattr(args, "identity", None),
        disable_brand_guardrails=getattr(args, "disable_brand_guardrails", False),
        allow_blocking=False,
    )
    from .generation_flow import assemble_generation_scratchpad

    scratchpad_preview = assemble_generation_scratchpad(preview_args, brand_dir=brand_dir, plan_wrapper=wrapper, plan=effective_plan)
    preview_checks = scratchpad_preview.get("checks") or {}
    blocking = dedupe_keep_order(list(report.get("errors") or []) + list(preview_checks.get("blocking") or []))
    learned_setup_warnings = dedupe_keep_order(
        [str(item).strip() for item in (effective_plan.get("learned_setup_warnings") or []) if str(item).strip()]
    )
    checks = {
        "blocking": blocking,
        "warnings": dedupe_keep_order(list(preview_checks.get("warnings") or []) + learned_setup_warnings),
    }
    critique_policy = build_critique_policy(
        critique_mode=critique_mode,
        entrypoint=entrypoint,
        blocking=blocking,
        allow_blocking=allow_blocking,
        bypass_reason=f"{entrypoint} ran with --allow-blocking despite blocking critique findings.",
    )
    if blocking and critique_policy.get("bypass_recorded"):
        state_status = "ready_with_bypass"
        next_step = "Blocking findings remain, but an explicit bypass is recorded for downstream generation."
    elif blocking:
        state_status = "needs_work"
        next_step = "Run build-generation-scratchpad when blocking issues are fixed."
    else:
        state_status = "approved_for_scratchpad"
        next_step = "Build the generation scratchpad."
    return {
        "schema_type": "plan_critique",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state": {
            "status": state_status,
            "owner": "critic_agent",
            "next_owner": "visual_composer",
        },
        "plan_path": str(Path(args.plan).expanduser().resolve()),
        "plan": effective_plan,
        "plan_validation": report,
        "prompt_review": scratchpad_preview.get("prompt_review") or {},
        "checks": checks,
        "learning_context": effective_plan.get("learning_context") or {},
        "critique_policy": critique_policy,
        "next_step": next_step,
    }


def check_identity_freshness(brand_dir: Path, manifest: dict, identity: dict) -> dict:
    """Check whether the brand identity needs a rebuild based on generation history and feedback signals."""
    versions = manifest.get("versions", {})
    total = len(versions)
    scored = [v for v in versions.values() if v.get("score") is not None]
    low_scored = [v for v in scored if (v.get("score") or 0) <= 2]
    high_scored = [v for v in scored if (v.get("score") or 0) >= 4]
    identity_version = identity.get("schema_version", 0)
    memory = load_iteration_memory(brand_dir)
    learnings = load_learnings_memory(brand_dir)
    brand_notes = memory.get("brand_notes") or []
    messaging_notes = memory.get("messaging_notes") or []
    negative_examples = memory.get("negative_examples") or []
    promoted_failure_patterns = list(learnings.get("failurePatterns") or [])
    promoted_composition_patterns = list(learnings.get("compositionPatterns") or [])

    _freshness = load_prompt_fragments().get("identity_freshness", {})
    _rebuild_interval = _freshness.get("rebuild_interval", 10)
    _low_score_ratio = _freshness.get("low_score_ratio_threshold", 0.5)
    _negative_threshold = _freshness.get("negative_examples_threshold", 3)
    _min_scored = _freshness.get("min_scored_versions", 3)

    reasons: list[str] = []
    # Check generation volume — rebuild after every N generations
    if total > 0 and total % _rebuild_interval == 0:
        reasons.append(f"Generated {total} versions since last identity build — identity may be stale.")
    # Check low-score ratio
    if len(scored) >= _min_scored and len(low_scored) / len(scored) > _low_score_ratio:
        reasons.append(f"{len(low_scored)}/{len(scored)} scored versions are 2/5 or below — identity preludes may be misguiding the model.")
    # Check if new negative examples accumulated
    if len(negative_examples) >= _negative_threshold:
        reasons.append(f"{len(negative_examples)} negative examples in iteration memory — identity should absorb these lessons.")
    if len(promoted_failure_patterns) >= 2:
        reasons.append(f"{len(promoted_failure_patterns)} promoted failure patterns are now durable enough to consider in the next identity rebuild.")
    if len(promoted_composition_patterns) >= 2:
        reasons.append(f"{len(promoted_composition_patterns)} promoted composition patterns suggest the identity can absorb stable winning setups.")
    # Check for missing new material types
    identity_snippets = set((identity.get("generation_guardrails") or {}).get("material_prompt_snippets", {}).keys())
    current_types = {"concept_illustration", "brand_scene", "data_card", "quote_card", "announcement_card", "process_card",
                     "content_card", "editorial_card", "podcast_cover", "podcast_banner"}
    missing = current_types - identity_snippets

    if missing:
        reasons.append(f"Identity is missing prompt snippets for: {', '.join(sorted(missing))}.")

    # Build a human-readable rebuild note explaining what lessons should be absorbed
    rebuild_note_lines: list[str] = []
    if promoted_failure_patterns:
        rebuild_note_lines.append("Absorb failure patterns into identity forbidden elements:")
        for fp in promoted_failure_patterns[:3]:
            text = fp.get("text", fp) if isinstance(fp, dict) else str(fp)
            rebuild_note_lines.append(f"  - {text}")
    if promoted_composition_patterns:
        rebuild_note_lines.append("Absorb composition wins into identity approved carriers:")
        for cp in promoted_composition_patterns[:3]:
            text = cp.get("text", cp) if isinstance(cp, dict) else str(cp)
            rebuild_note_lines.append(f"  - {text}")
    if negative_examples:
        rebuild_note_lines.append(f"Review {len(negative_examples)} negative examples from iteration memory for recurring anti-patterns.")
    if missing:
        rebuild_note_lines.append(f"Add prompt snippets for new material types: {', '.join(sorted(missing))}.")

    return {
        "needs_rebuild": len(reasons) > 0,
        "reasons": reasons,
        "rebuild_note": "\n".join(rebuild_note_lines) if rebuild_note_lines else "",
        "absorbable_learnings": {
            "failure_patterns": [
                (fp.get("text", fp) if isinstance(fp, dict) else str(fp))
                for fp in promoted_failure_patterns[:5]
            ],
            "composition_patterns": [
                (cp.get("text", cp) if isinstance(cp, dict) else str(cp))
                for cp in promoted_composition_patterns[:5]
            ],
            "missing_snippets": sorted(missing) if missing else [],
        },
        "total_versions": total,
        "scored_versions": len(scored),
        "low_scored": len(low_scored),
        "high_scored": len(high_scored),
        "negative_examples": len(negative_examples),
        "promoted_failure_patterns": len(promoted_failure_patterns),
        "promoted_composition_patterns": len(promoted_composition_patterns),
        "identity_schema_version": identity_version,
        "missing_snippets": sorted(missing) if missing else [],
    }


def build_improvement_questions(brand_dir: Path, profile: dict, identity: dict, manifest: dict) -> list[dict]:
    """Generate contextual questions the agent should ask to improve the brand over time.

    Returns a list of question dicts with: question, category, priority (1-5), context.
    Questions are contextual — they depend on what's been generated, what scored well/poorly,
    and what brand data is missing.
    """
    questions: list[dict] = []
    versions = manifest.get("versions", {})
    scored = {k: v for k, v in versions.items() if v.get("score") is not None}
    memory = load_iteration_memory(brand_dir)
    messaging = memory.get("messaging_notes") or []
    brand_notes = memory.get("brand_notes") or []
    material_types_used = set()
    for v in versions.values():
        mt = v.get("material_type")
        if mt:
            material_types_used.add(mt)

    # Phase 1: Brand foundation questions (always relevant early)
    description = profile.get("description") or identity.get("brand", {}).get("summary") or ""
    if len(description) < 50:
        questions.append({
            "question": "Can you describe what your product/brand does and who it serves in 2-3 sentences? This helps the agent generate materials that reflect your actual product, not generic marketing.",
            "category": "brand_foundation",
            "priority": 5,
            "context": "Brand description is missing or very short.",
        })

    keywords = (identity.get("identity_core") or {}).get("tone_words") or []
    if len(keywords) < 3:
        questions.append({
            "question": "What 3-5 words describe how your brand should feel? (e.g., 'calm, technical, trustworthy' or 'bold, playful, energetic')",
            "category": "brand_foundation",
            "priority": 4,
            "context": "Tone words are sparse — the agent can't differentiate your brand feeling from generic defaults.",
        })

    # Phase 2: Visual direction questions (after first few generations)
    if len(versions) >= 2:
        illustration_types_used = material_types_used & {
            "concept-illustration",
            "system-explainer-illustration",
            "editorial-metaphor-illustration",
            "brand-scene",
            "illustrated-brand-world",
            "feature-illustration",
        }
        ui_types_used = material_types_used & {"browser-illustration", "landing-hero", "product-banner"}
        if len(ui_types_used) > 0 and len(illustration_types_used) == 0:
            questions.append({
                "question": "So far we've only generated product UI materials. Would you like to explore brand illustrations — concept art, atmospheric scenes, or visual metaphors that represent your brand's values without showing product UI?",
                "category": "visual_direction",
                "priority": 4,
                "context": f"Generated types so far: {', '.join(sorted(material_types_used))}. No illustration types yet.",
            })

        refs = list((brand_dir / "references").glob("*")) if (brand_dir / "references").is_dir() else []
        if len(refs) > 0 and all(not str(r.name).startswith("illustration") for r in refs):
            questions.append({
                "question": "Your reference images appear to be product screenshots only. Would you like to add illustration-style or brand-world reference images? These help the model produce non-UI materials that don't default to screenshot styling.",
                "category": "visual_direction",
                "priority": 3,
                "context": f"Found {len(refs)} references, all appear to be UI screenshots.",
            })

    # Phase 3: Messaging questions (after some content)
    if len(versions) >= 3 and not messaging:
        questions.append({
            "question": "You've generated several materials but haven't set any messaging yet. What's your primary tagline or value proposition? (e.g., 'The intelligence layer for prompt curation' or 'Build better with shared knowledge')",
            "category": "messaging",
            "priority": 4,
            "context": "No messaging notes in memory. Copy-bearing materials will use generic or invented text.",
        })

    # Phase 4: Quality improvement questions (after scored feedback)
    low_scored = [(k, v) for k, v in scored.items() if (v.get("score") or 0) <= 2]
    negative_examples = memory.get("negative_examples") or []
    _neg_versions = {ne.get("version") for ne in negative_examples}
    _uncaptured_low = [(k, v) for k, v in low_scored if k not in _neg_versions]
    if len(low_scored) >= 2:
        low_types = set(v.get("material_type", "unknown") for _, v in low_scored)
        low_notes = [v.get("notes", "") for _, v in low_scored if v.get("notes")]
        if _uncaptured_low:
            # Some low-scored versions don't have auto-captured feedback yet
            questions.append({
                "question": f"Several generated materials scored poorly ({', '.join(sorted(low_types))}). What specifically felt wrong? Common issues: too generic, wrong mood, missing brand anchor, or invented copy. Your answer will be saved as a negative example to prevent repetition.",
                "category": "quality_feedback",
                "priority": 5,
                "context": f"{len(low_scored)} versions scored ≤2. Notes: {'; '.join(low_notes[:3]) or 'none given'}.",
            })
        else:
            # All low-scored versions already have auto-captured feedback — downgrade to informational
            _captured_summaries = [ne.get("summary", "") for ne in negative_examples if ne.get("version") in {k for k, _ in low_scored}]
            questions.append({
                "question": f"Quality feedback has been auto-captured for {len(low_scored)} low-scored versions ({', '.join(sorted(low_types))}). Review the iteration memory if you want to refine the feedback. No action needed unless you disagree with the captured notes.",
                "category": "quality_feedback",
                "priority": 2,
                "context": f"Auto-captured: {'; '.join(_captured_summaries[:3]) or 'see iteration memory'}.",
                "auto_resolved": True,
            })

    # Phase 5: Brand assets questions
    brand_assets = identity.get("brand_assets") or {}
    if not brand_assets.get("icon") and not brand_assets.get("lockup"):
        questions.append({
            "question": "Do you have a logo, icon, or wordmark file? If so, tell me where it is — I'll register it as a brand asset so it can appear as an anchor in generated materials.",
            "category": "brand_assets",
            "priority": 3,
            "context": "No brand assets (icon, wordmark, lockup) registered in identity.",
        })

    # Phase 6: Target audience / platform questions
    if len(versions) >= 5 and "social" in material_types_used:
        questions.append({
            "question": "Which platforms do you primarily share content on? (LinkedIn, X/Twitter, Instagram, YouTube) This affects optimal dimensions, tone, and content style.",
            "category": "distribution",
            "priority": 2,
            "context": "Social materials generated but no platform preference recorded.",
        })

    # Sort by priority (highest first)
    questions.sort(key=lambda q: -q["priority"])
    return questions


def select_plan_roles(candidates: dict, picks: dict[str, str]) -> tuple[list[dict], list[str]]:
    selected: list[dict] = []
    missing_required: list[str] = []
    used_sources: set[str] = set()
    prefer_unique_sources = candidates.get("prefer_unique_sources", True)
    for role in candidates.get("priority") or ROLE_PACK_TAG_PRIORITY:
        role_candidates = candidates.get("candidates", {}).get(role) or []
        pick_value = picks.get(role)
        picked = None
        if pick_value:
            pick_path = Path(pick_value).expanduser()
            if pick_path.exists():
                picked = {
                    "role": role,
                    "role_help": next((item.get("role_help") for item in role_candidates if item.get("role_help")), ""),
                    "source_key": f"custom-{pick_path.stem}",
                    "source_name": pick_path.name,
                    "notes": "custom explicit path",
                    "path": str(pick_path.resolve()),
                    "asset_kind": path_media_kind(pick_path),
                    "used_role_asset": True,
                }
            else:
                for item in role_candidates:
                    if item["source_key"] == pick_value:
                        picked = dict(item)
                        break
        else:
            preferred_candidates = [
                item for item in role_candidates
                if not item.get("translation_only") and source_risk_rank(item.get("direct_generation_risk")) < source_risk_rank("high")
            ] or [
                item for item in role_candidates if source_risk_rank(item.get("direct_generation_risk")) < source_risk_rank("high")
            ] or [
                item for item in role_candidates if not item.get("translation_only")
            ] or role_candidates
            for item in preferred_candidates:
                if not prefer_unique_sources or item["source_key"] not in used_sources:
                    picked = dict(item)
                    break
            if not picked and preferred_candidates:
                picked = dict(preferred_candidates[0])

        if not picked:
            if role in (candidates.get("required_roles") or []):
                missing_required.append(role)
            continue
        selected.append(picked)
        if prefer_unique_sources:
            used_sources.add(picked["source_key"])
    return selected, missing_required


def extract_plan_payload(payload: dict) -> dict:
    if payload.get("schema_type") == "plan_draft" and isinstance(payload.get("plan"), dict):
        return payload["plan"]
    return payload


def load_plan_payload(path: Path) -> tuple[dict, dict]:
    payload = load_json_file(path)
    return payload, extract_plan_payload(payload)


def classify_workflow_route_smart(material_type: str | None, goal: str = "", request: str = "", has_motion_reference: bool = False, set_scope: bool = False, *, route_override: str | None = None) -> dict:
    """Route classification using keyword scoring.  If *route_override* is
    provided (the agent picked a route key from the candidates returned by
    ``route-request --format json``), that route is used directly."""
    rules = load_workflow_router_rules()
    routes = rules.get("routes") or []

    # Agent-selected route override
    if route_override:
        route = next((r for r in routes if r["key"] == route_override), None)
        if route:
            return {
                "route_key": route_override,
                "route": route,
                "material_key": role_pack_material_key(material_type),
                "llm_routed": False,
                "score": 1.0,
                "method": "agent_override",
                "score_vector": {},
            }

    route = next((item for item in routes if item.get("key") == "generative_explore"), {}) or {
        "key": "generative_explore",
        "label": "generative explore",
        "specialists": ["brand_director", "visual_composer", "critic_agent"],
        "required_assets": [],
        "next_commands": [],
        "notes": "",
    }
    return {
        "route_key": "generative_explore",
        "route": route,
        "material_key": role_pack_material_key(material_type),
        "llm_routed": False,
        "score": 0.0,
        "method": "default",
        "score_vector": {},
    }


def build_route_candidates(material_type: str | None, goal: str = "", request: str = "") -> list[dict]:
    """Return scored route candidates for the calling agent to choose from.

    Instead of making a nested LLM call, this returns the route options with
    context so the agent (which IS an LLM) can pick the best one.
    """
    rules = load_workflow_router_rules()
    routes = rules.get("routes") or []
    candidates = []
    for r in routes:
        candidates.append({
            "key": r["key"],
            "label": r.get("label") or r["key"],
            "notes": r.get("notes") or "",
            "specialists": r.get("specialists") or [],
            "required_assets": r.get("required_assets") or [],
        })
    return candidates


def preferred_material_engine(material_type: str) -> str:
    return "generate"
