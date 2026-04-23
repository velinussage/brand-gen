from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import subprocess
import sys
import time

from .blackboard import get_blackboard_learning_warnings
from .critique_policy import build_critique_policy, normalize_critique_policy
from .custom_scratchpad import resolve_model_override as _resolve_custom_scratchpad_model_override
from .inspiration_board import persist_inspiration_source_selection, persist_plan_inspiration_board
from .iteration_memory import (
    add_iteration_note,
    capture_feedback_into_iteration_memory,
    load_iteration_memory,
    save_iteration_memory,
)
from .runtime import *
from .runtime_models import recommend_text_model
from .material_planning import *
from .plan_validation import detect_exact_text_request, plan_declares_deterministic_text_strategy
from .reference_analysis import (
    build_reference_analysis_inputs as _build_reference_analysis_inputs,
    build_reference_analysis_snippet as _build_reference_analysis_snippet,
    check_inspiration_pipeline_status as _check_inspiration_pipeline_status,
    ensure_reference_analysis as _ensure_reference_analysis,
    extract_reference_image_stats as _extract_reference_image_stats,
    reference_analysis_confidence as _reference_analysis_confidence,
    reference_analysis_mode as _reference_analysis_mode,
    reference_analysis_review_notes as _reference_analysis_review_notes,
)
from .media_board import generate_compare_board
from .agent_review import write_agent_visual_review_packet
from .pipeline_qa import write_pipeline_qa_report
from .run_ledger import append_run_event
from .vlm_critique import (
    refine_prompt_from_vlm_critique as _refine_prompt_from_vlm_critique,
    run_vlm_critique as _run_vlm_critique,
)


@contextmanager
def _manifest_write_lock(brand_dir: Path):
    lock_path = Path(str(get_manifest_path(brand_dir)) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _reserve_manifest_version(
    brand_dir: Path,
    *,
    material_type: str,
    workflow_id: str,
    tag: str,
) -> str:
    with _manifest_write_lock(brand_dir):
        manifest = load_manifest(brand_dir)
        vnum = next_version_num(manifest, brand_dir)
        vid = f"v{vnum:03d}"
        manifest.setdefault("versions", {})
        manifest["versions"].setdefault(
            vid,
            {
                "status": "reserved",
                "material_type": material_type,
                "tag": tag,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "workflow_id": workflow_id,
            },
        )
        save_manifest(manifest, brand_dir)
        return vid


def _update_manifest_version(brand_dir: Path, version_id: str, updates: dict) -> tuple[dict, dict]:
    with _manifest_write_lock(brand_dir):
        manifest = load_manifest(brand_dir)
        manifest.setdefault("versions", {})
        current = dict((manifest.get("versions") or {}).get(version_id) or {})
        current.update(updates or {})
        manifest["versions"][version_id] = current
        save_manifest(manifest, brand_dir)
        return manifest, current


def build_base_image_edit_policy(material_type: str | None = None) -> str:
    material_label = str(material_type or "material").strip().replace("-", " ")
    return (
        f"Base-image edit policy: Treat the supplied base image as authoritative truth for the {material_label} layout, "
        "card geometry, screenshot inset, and any readable deterministic text. Preserve that structure exactly unless the "
        "user explicitly asked to replace it. Only add branded polish in surrounding fields such as background texture, "
        "motif, lighting, or carrier finish. Do not redraw the UI, do not paraphrase or hallucinate text, do not place "
        "decorative elements over the screenshot or title area, and keep every element fully inside the card bounds."
    )


def filter_reference_paths_for_base_image_edit(
    paths: list[Path],
    role_pack: list[dict] | None = None,
) -> tuple[list[Path], bool]:
    role_pack = role_pack or []
    motif_paths = {
        str(Path(item.get("path", "")).expanduser().resolve())
        for item in role_pack
        if str(item.get("role") or "").strip() == "motif" and item.get("path")
    }
    if not motif_paths:
        return [], bool(paths)
    filtered = [path for path in paths if str(Path(path).expanduser().resolve()) in motif_paths]
    return dedupe_paths(filtered), len(filtered) != len(paths)


def resolve_base_image_reference_path(base_image: str | None) -> Path | None:
    raw = str(base_image or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.exists():
        raise SystemExit(f"ERROR: Base image not found: {raw}")
    if path_media_kind(path) != "image":
        raise SystemExit(f"ERROR: --base-image must point to a supported image asset: {raw}")
    return path.resolve()


def build_base_image_reference_role(base_image_path: Path) -> dict:
    resolved = Path(base_image_path).expanduser().resolve()
    return {
        "role": "product_truth",
        "role_help": "Use this base image as authoritative carrier proof and preserve its readable screenshot/text truth.",
        "source_key": f"base-image-{resolved.stem}",
        "source_name": resolved.name,
        "notes": "authoritative base-image carrier proof",
        "path": str(resolved),
        "asset_kind": "image",
        "used_role_asset": True,
        "reference_quality": "custom-proof",
        "reference_quality_reasons": ["base image supplied by the user"],
    }


def ensure_base_image_reference_role(
    role_pack_override: dict | None,
    base_image_path: Path | None,
) -> tuple[dict | None, bool]:
    if base_image_path is None:
        return role_pack_override, False
    roles = [dict(item) for item in ((role_pack_override or {}).get("roles") or [])]
    resolved_base = str(base_image_path)
    if any(
        str(item.get("role") or "").strip() == "product_truth"
        and item.get("path")
        and str(Path(item["path"]).expanduser().resolve()) == resolved_base
        for item in roles
    ):
        return role_pack_override, False
    if any(str(item.get("role") or "").strip() == "product_truth" for item in roles):
        return role_pack_override, False
    override = dict(role_pack_override or {})
    override["roles"] = roles + [build_base_image_reference_role(base_image_path)]
    required_roles = list(override.get("required_roles") or [])
    if "product_truth" not in required_roles:
        override["required_roles"] = ["product_truth"] + required_roles
    priority = list(override.get("priority") or [])
    if "product_truth" not in priority:
        override["priority"] = ["product_truth"] + priority
    return override, True


def _is_non_bypassable_generation_blocker(issue: str) -> bool:
    lower = str(issue or "").strip().lower()
    return "requires at least one reference asset" in lower


def assemble_generation_scratchpad(
    args,
    *,
    brand_dir: Path,
    plan_wrapper: dict,
    plan: dict,
) -> dict:
    requested_material_type = args.material_type or plan.get("material_type") or "logo"
    material_type = normalize_material_type(requested_material_type)
    tag = args.tag or plan.get("tag") or requested_material_type or "brand"
    raw_prompt = args.prompt or plan.get("prompt_seed") or ""
    if not raw_prompt.strip():
        raise SystemExit("ERROR: build-generation-scratchpad requires --prompt or --plan with a prompt_seed.")

    workflow_id = resolve_workflow_id(plan_wrapper, plan)
    if plan and not (plan.get("inspiration_board") or {}).get("selected_reference_ids"):
        plan["workflow_id"] = workflow_id
        persist_plan_inspiration_board(brand_dir, plan, workflow_id=workflow_id)

    base_image = getattr(args, "base_image", None) or ""
    base_image_reference_path = resolve_base_image_reference_path(base_image)
    plan_role_pack_override = build_role_pack_override_from_plan(plan) if plan else None
    plan_role_pack_override, base_image_role_added = ensure_base_image_reference_role(
        plan_role_pack_override,
        base_image_reference_path,
    )
    plan_reference_paths = [Path(item["path"]).expanduser().resolve() for item in ((plan_role_pack_override or {}).get("roles") or []) if path_media_kind(item.get("path", "")) == "image"]
    reference_paths = expand_reference_paths(getattr(args, "image", None), getattr(args, "reference_dir", None))
    if base_image_reference_path is not None:
        reference_paths = dedupe_paths(reference_paths + [base_image_reference_path])
    reference_paths = dedupe_paths(reference_paths + plan_reference_paths)
    requested_mode = args.mode if getattr(args, "mode", "auto") != "auto" else (plan.get("mode") or "auto")
    mode_requested_explicitly = str(getattr(args, "mode", "auto") or "").strip().lower() != "auto"
    workflow_mode = resolve_workflow_mode(requested_mode, reference_paths)
    generation_mode = resolve_generation_mode(material_type, getattr(args, "generation_mode", "auto"))

    profile_path, identity_path, profile_data, identity_data = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile_data,
        identity=identity_data,
        brand_gen_dir=brand_gen_dir,
    )
    pre_prompt_reference_paths = dedupe_paths(
        list(reference_paths)
        + [Path(item["path"]).expanduser().resolve() for item in ((plan_role_pack_override or {}).get("roles") or []) if path_media_kind(item.get("path", "")) == "image"]
    )
    reference_analysis = ensure_reference_analysis(
        brand_dir,
        profile=profile_data,
        identity=identity_data,
        reference_paths=pre_prompt_reference_paths,
        role_pack_roles=(plan_role_pack_override or {}).get("roles") or [],
        material_type=material_type,
        skip_extraction=bool(getattr(args, "skip_extraction", False)),
        refresh_extraction=bool(getattr(args, "refresh_reference_analysis", False)),
    )
    reference_analysis_mode = _reference_analysis_mode(reference_analysis)
    reference_analysis_confidence = _reference_analysis_confidence(reference_analysis)
    render_backend = "html" if str(getattr(args, "render_backend", None) or "").strip().lower() == "html" else "native"
    prompt_context = build_effective_prompt(
        profile_data,
        identity_data,
        raw_prompt,
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        brand_dir=brand_dir,
        material_type=material_type,
        workflow_mode=workflow_mode,
        disable_brand_guardrails=getattr(args, "disable_brand_guardrails", False),
        role_pack_override=plan_role_pack_override,
        reference_analysis=reference_analysis,
        selected_inspiration_sources=list(plan.get("selected_inspiration_sources") or []),
        selected_inspiration_ids=list(plan.get("selected_inspiration_ids") or []),
        selected_mechanic_ids=list(plan.get("selected_mechanic_ids") or []),
        selected_mechanic_labels=list(plan.get("selected_mechanic_labels") or []),
        inspiration_selection_reason=str(plan.get("inspiration_selection_reason") or ""),
        inspiration_selection_mode=str(plan.get("inspiration_selection_mode") or ""),
        render_backend=render_backend,
        source_url=getattr(args, "source_url", None) or "",
        entity_type=getattr(args, "entity_type", None) or "",
        selected_surface_strategy=plan.get("selected_surface_strategy") or "",
        selected_surface_strategy_label=plan.get("selected_surface_strategy_label") or "",
        purpose=plan.get("purpose") or "",
        target_surface=plan.get("target_surface") or "",
        aesthetic_archetype=plan.get("aesthetic_archetype") if isinstance(plan.get("aesthetic_archetype"), dict) else None,
        prompt_subject=str(plan.get("prompt_subject") or ""),
        prompt_style_descriptors=str(plan.get("prompt_style_descriptors") or ""),
        prompt_lighting=str(plan.get("prompt_lighting") or ""),
        prompt_camera=str(plan.get("prompt_camera") or ""),
        prompt_composition=str(plan.get("prompt_composition") or ""),
        prompt_details=str(plan.get("prompt_details") or ""),
        visual_density=plan.get("visual_density"),
        aesthetic_commitment=plan.get("aesthetic_commitment") or "",
    )
    prompt_context["reference_analysis_mode"] = reference_analysis_mode
    prompt_context["reference_analysis_confidence"] = reference_analysis_confidence
    prompt_context["render_backend"] = render_backend
    prompt_context["source_url"] = getattr(args, "source_url", None) or ""
    prompt_context["entity_type"] = getattr(args, "entity_type", None) or ""
    prompt_context["selected_surface_strategy"] = plan.get("selected_surface_strategy") or ""
    selected_reference_ids = list(
        plan.get("selected_reference_ids")
        or ((plan.get("inspiration_board") or {}).get("selected_reference_ids") or [])
    )
    selected_inspiration_ids, inspiration_board_path = persist_inspiration_source_selection(
        brand_dir,
        list(prompt_context.get("inspiration_source_records") or []),
        workflow_id=workflow_id,
        direction_id=((plan.get("inspiration_board") or {}).get("direction_id") if isinstance(plan, dict) else None),
    )

    role_pack_paths = [Path(path) for path in prompt_context.get("reference_role_pack_paths", [])]
    role_pack_motion_paths = [Path(path) for path in prompt_context.get("reference_role_pack_motion_paths", [])]
    selected_role_names = [str(item.get("role") or "").strip() for item in (prompt_context.get("reference_role_pack") or []) if str(item.get("role") or "").strip()]
    required_roles = prompt_context.get("reference_role_pack_required_roles") or []
    missing_required_roles = [role for role in required_roles if role not in selected_role_names]
    motion_reference = Path(args.motion_reference).expanduser().resolve() if getattr(args, "motion_reference", None) else None

    # Auto-inject brand assets (logo/icon/wordmark) as reference images
    # so the model can see the actual brand mark, not just a text description.
    brand_asset_paths = resolve_brand_asset_paths(profile_data, identity_data, brand_dir=brand_dir)
    if brand_asset_paths:
        # Prepend brand assets so they appear first in the reference list
        reference_paths = dedupe_paths(brand_asset_paths + list(reference_paths))

    all_context_refs = dedupe_paths(list(reference_paths) + role_pack_paths)

    blocking_issues: list[str] = []
    warnings: list[str] = []
    _identity_messaging = (identity_data or {}).get("messaging") or {}
    _forbidden_claims = [str(item).strip() for item in (_identity_messaging.get("forbidden_claims") or []) if str(item).strip()]
    if _forbidden_claims and raw_prompt:
        _lowered_prompt = raw_prompt.lower()
        for _claim in _forbidden_claims:
            _needle = _claim.lower()
            if _needle and _needle in _lowered_prompt:
                blocking_issues.append(
                    f"Prompt contains a forbidden messaging claim: '{_claim}'. Remove or rephrase before generating."
                )
    if base_image_role_added:
        warnings.append("Base image auto-registered as a `product_truth` reference so reference analysis and QA can see the carrier proof.")
    if workflow_mode == "reference" and not reference_paths and not mode_requested_explicitly:
        workflow_mode = "inspiration"
        warnings.append(
            "Reference mode had zero effective references, so the scratchpad rerouted to inspiration mode instead of silently continuing under a bypass."
        )
    if workflow_mode in {"reference", "hybrid"} and not reference_paths:
        blocking_issues.append(
            f"Mode '{workflow_mode}' requires at least one reference asset (an explicit ref, role-pack ref, or --base-image carrier)."
        )
    if motion_reference and not reference_paths:
        blocking_issues.append("--motion-reference requires at least one --image start frame or reference asset.")
    if missing_required_roles:
        warnings.append("Missing required role refs: " + ", ".join(missing_required_roles))
    else:
        priority_roles = [
            str(role).strip()
            for role in (prompt_context.get("reference_role_pack_priority") or [])
            if str(role).strip()
        ]
        optional_priority_roles = [role for role in priority_roles if role not in required_roles]
        selected_optional_roles = [role for role in selected_role_names if role in optional_priority_roles]
        if optional_priority_roles and not selected_optional_roles:
            warnings.append(
                "Optional composition/application role refs are absent; generation can proceed, but framing guidance is narrower than usual."
            )

    # --- Inspiration readiness: HARD BLOCK for hybrid/inspiration modes when
    # sources are configured but not extracted, or when analysis is deterministic-only.
    # The retrospective on v121/v123/v124 showed the system proceeded anyway with
    # warnings that the critic did not enforce; pipeline-level blocking fixes that.
    # Pass --allow-blocking to record an explicit bypass.
    inspiration_status = check_inspiration_pipeline_status(brand_gen_dir, active_brand, workflow_mode)
    _inspiration_pending_unextracted = any(
        "not extracted yet" in str(w).lower()
        for w in (inspiration_status.get("warnings") or [])
    )
    if not inspiration_status["ok"]:
        if workflow_mode in {"hybrid", "inspiration"} and _inspiration_pending_unextracted:
            blocking_issues.append(
                f"Inspiration-readiness block: {workflow_mode} mode requires extracted inspiration, "
                f"but sources are configured and unextracted. "
                f"Run `bgen extract-inspiration` and `bgen consolidate-inspiration` before planning, "
                f"or pass --allow-blocking to record a bypass."
            )
            for w in inspiration_status.get("warnings", []):
                blocking_issues.append(f"  inspiration: {w}")
            for s in inspiration_status.get("suggestions", []):
                blocking_issues.append(f"  → {s}")
        else:
            for w in inspiration_status.get("warnings", []):
                warnings.append(f"Inspiration: {w}")
            for s in inspiration_status.get("suggestions", []):
                warnings.append(f"  → {s}")
    for warning in (reference_analysis.get("warnings") or []):
        warnings.append(f"Reference analysis: {warning}")
    for warning in (prompt_context.get("reference_role_assignment_warnings") or []):
        warnings.append(f"Reference-role assignment: {warning}")
    if reference_analysis_mode == "deterministic_only":
        if workflow_mode in {"hybrid", "inspiration"} and prompt_context["material_prompt_key"] not in INTERFACE_MATERIAL_KEYS:
            blocking_issues.append(
                f"Reference-analysis block: analysis is deterministic-only "
                f"(confidence: {reference_analysis_confidence}) in {workflow_mode} mode on "
                f"non-interface material '{material_type}'. "
                f"Run `bgen consolidate-inspiration` to get a richer analysis, "
                f"or pass --allow-blocking to record a bypass."
            )
        else:
            warnings.append(
                f"Reference analysis is deterministic-only (confidence: {reference_analysis_confidence}); treat reference-role translation as approximate."
            )
    elif reference_analysis_mode == "unavailable":
        warnings.append("Reference analysis is unavailable; treat reference-role guidance as low-confidence.")

    # --- Self-referential composition drift: block when all composition refs come
    # from prior internal versions (v\d+-*) AND external inspiration is configured
    # but unextracted. Retrospective showed v123 built on v121 built on v016/v058
    # created drift. Pipeline catches this before it compounds.
    import re as _re_self_ref
    _composition_role_refs = [
        Path(str(item.get("path") or "")).name
        for item in (prompt_context.get("reference_role_pack") or [])
        if str(item.get("role") or "") in {"composition", "application"}
    ]
    _composition_role_refs = [name for name in _composition_role_refs if name]
    if (
        workflow_mode in {"hybrid", "inspiration"}
        and _composition_role_refs
        and all(_re_self_ref.match(r"^v\d+", name) for name in _composition_role_refs)
        and _inspiration_pending_unextracted
    ):
        blocking_issues.append(
            f"Self-referential composition drift: all composition/application refs are "
            f"prior internal versions ({', '.join(_composition_role_refs[:4])}) but "
            f"external inspiration sources are configured and unextracted. "
            f"Extract inspiration and rebuild the plan, "
            f"or pass --allow-blocking to record a bypass."
        )

    # --- Mode-underperforming and source-version-rejected: escalate the blackboard
    # learning signals from advisory warnings to blocking issues. Retrospective
    # showed the learning warnings were emitted but the run proceeded anyway.
    _source_version_for_learn = getattr(args, "source_version", None) or plan.get("source_version") or ""
    _learned_warnings = get_blackboard_learning_warnings(
        brand_dir,
        material_type,
        proposed_mode=workflow_mode,
        has_reference_roles=bool(prompt_context.get("reference_role_pack")),
        source_version=_source_version_for_learn,
    )
    for _lw in _learned_warnings:
        _lw_low = _lw.lower()
        if "underperforming for this material recently" in _lw_low:
            blocking_issues.append(
                f"Learnings block: {_lw} Switch to the winning setup from learnings.json, "
                f"or pass --allow-blocking to record a bypass."
            )
        elif "was recently rejected; avoid deriving" in _lw_low:
            blocking_issues.append(
                f"Source-lineage block: {_lw} Choose a different source_version, "
                f"or pass --allow-blocking to record a bypass."
            )
        else:
            warnings.append(f"Blackboard learning: {_lw}")

    # --- Source critique: auto-upgrade model on iteration when text issues found ---
    _source_critique_model_rec = None
    _source_version_for_critique = getattr(args, "source_version", None) or plan.get("source_version") or ""
    if _source_version_for_critique and not args.model:
        try:
            _src_manifest = load_manifest(brand_dir)
            _src_entry = (_src_manifest.get("versions") or {}).get(_source_version_for_critique) or {}
            _src_critique_path = _src_entry.get("vlm_critique_path")
            if _src_critique_path and Path(_src_critique_path).exists():
                _src_critique = json.loads(Path(_src_critique_path).read_text())
                _source_critique_model_rec = recommend_text_model(
                    _src_critique,
                    _src_entry.get("model", ""),
                    material_type,
                    bool(reference_paths),
                )
                if _source_critique_model_rec:
                    warnings.append(
                        f"Iterating from {_source_version_for_critique}: text issues found. "
                        f"Model switched to {_source_critique_model_rec} for better text rendering."
                    )
        except (json.JSONDecodeError, OSError):
            pass

    base_image = getattr(args, "base_image", None) or ""
    render_backend = "html" if str(getattr(args, "render_backend", None) or "").strip().lower() == "html" else "native"
    _custom_override = _resolve_custom_scratchpad_model_override(brand_dir, material_type)
    _custom_model = _custom_override.get("model") if not args.model else None
    if _custom_override.get("mode") and not mode_requested_explicitly:
        workflow_mode = resolve_workflow_mode(_custom_override["mode"], reference_paths)
        warnings.append(
            f"Custom scratchpad override: mode forced to '{_custom_override['mode']}' for material '{material_type}'."
        )
    _default_model = resolve_default_model(
        material_type,
        generation_mode,
        workflow_mode,
        all_context_refs,
        prompt_context["material_prompt_key"],
        has_motion_reference=bool(motion_reference),
        has_base_image=bool(base_image),
    )
    _preserve_default_model = material_uses_canonical_gpt_image_2(
        material_type,
        generation_mode,
        has_base_image=bool(base_image),
        has_motion_reference=bool(motion_reference),
    )
    _learned_model = (
        resolve_learned_model(material_type, brand_dir)
        if not (_source_critique_model_rec or args.model or _custom_model or _preserve_default_model)
        else None
    )
    model = _source_critique_model_rec or args.model or _custom_model or _learned_model or _default_model
    if _preserve_default_model and not (_source_critique_model_rec or args.model or _custom_model):
        warnings.append(
            f"Canonical material renderer preserved: '{material_type}' stays on '{_default_model}' unless explicitly overridden."
        )
    if _learned_model and model == _learned_model:
        warnings.append(
            f"Learnings override: modelPreferences promoted '{_learned_model}' "
            f"for material '{material_type}' over material_config default."
        )
    if _custom_model and model == _custom_model:
        warnings.append(
            f"Custom scratchpad override: model set to '{model}' for material '{material_type}'."
        )
    model_config = MODELS.get(generation_mode, {}).get(model)
    if not model_config:
        blocking_issues.append(f"Model '{model}' is not available for {generation_mode} generation.")
        model_config = {}
    elif motion_reference and not model_supports_motion_reference(model_config):
        blocking_issues.append(f"Model '{model}' does not support motion references.")

    aspect_ratio = resolve_default_aspect_ratio(material_type, getattr(args, "aspect_ratio", None), model_config or {})
    prompt_context["output_aspect_ratio"] = aspect_ratio or ""
    prompt_context["output_resolution"] = str(getattr(args, "resolution", None) or "")
    prompt_review = review_prompt_architecture(
        profile_data,
        identity_data,
        raw_prompt,
        prompt_context,
        material_type=material_type,
        workflow_mode=workflow_mode,
        token_block=prompt_context.get("token_block", ""),
        generation_mode=generation_mode,
    )
    reference_tag_context = build_reference_tag_context(
        model,
        generation_mode,
        reference_paths,
        prompt_context.get("reference_role_pack") or [],
    )
    if (
        detect_exact_text_request(plan) or detect_exact_text_request(raw_prompt)
    ) and render_backend != "html" and not plan_declares_deterministic_text_strategy(plan):
        blocking_issues.append(
            "Exact-text rendering block: this brief asks for exact/verbatim text, but the run is using the native image backend. "
            "Use render_backend=html or declare text_rendering_strategy=html/svg/composite so text is rendered deterministically before generation."
        )

    effective_prompt = prompt_review["refined_prompt"]
    execution_prompt = prompt_review.get("execution_prompt") or effective_prompt
    if base_image:
        base_image_policy = build_base_image_edit_policy(material_type)
        effective_prompt = f"{effective_prompt.rstrip()}\n\n{base_image_policy}"
        execution_prompt = f"{execution_prompt.rstrip()}\n\n{base_image_policy}"
        warnings.append("Base image supplied: generation is constrained to carrier polish around authoritative screenshot/text truth.")
    tagged_prompt_suffix = reference_tag_context.get("prompt_suffix", "").strip()
    if tagged_prompt_suffix:
        execution_prompt = f"{execution_prompt.rstrip()}\n\n{tagged_prompt_suffix}"
    supports_reference_images = model_supports_reference_images(model_config, generation_mode) if model_config else False
    passed_refs = list(all_context_refs)
    if base_image and passed_refs:
        passed_refs, refs_trimmed = filter_reference_paths_for_base_image_edit(
            passed_refs,
            prompt_context.get("reference_role_pack") or [],
        )
        if refs_trimmed:
            warnings.append(
                "Base image supplied: limiting passed image refs to motif assets so the model polishes the carrier instead of redrawing screenshot truth."
            )
    if model_config and not supports_reference_images and all_context_refs:
        passed_refs = []
        warnings.append(f"Model '{model}' does not accept image refs in the current wrapper; refs are used for prompt routing/context only.")
    if model_config and model_supports_reference_tags(model_config) and reference_tag_context.get("passed_refs"):
        passed_refs = dedupe_paths(reference_tag_context["passed_refs"])
    if generation_mode == "video" and len(passed_refs) > 1:
        warnings.append("Video generation supports one start frame; only the first reference asset will be passed to the model.")
        passed_refs = passed_refs[:1]
    if generation_mode == "video" and getattr(args, "duration", None) and model_config and not (model_config.get("field_map", {}) or {}).get("duration") and "duration" not in (model_config.get("defaults", {}) or {}):
        warnings.append(f"Model '{model}' does not expose duration control; --duration will be ignored.")
    profile_assets = (
        (identity_data.get("brand_assets") or {})
        if isinstance(identity_data, dict) and (identity_data.get("brand_assets") or {})
        else ((profile_data.get("brand_assets") or {}) if isinstance(profile_data, dict) else {})
    )
    approved_assets = [str(profile_assets.get(key) or "").strip() for key in ("icon", "wordmark", "lockup")]
    model_transport_reference_paths = [str(path) for path in passed_refs]
    authoritative_reference_paths = dedupe_keep_order(
        ([str(base_image_reference_path)] if base_image_reference_path else [])
        + model_transport_reference_paths
    )
    policy_setup_risks = evaluate_policy_setup_risks(
        material_type,
        brand_policy=(plan.get("brand_anchor_policy") or normalize_material_brand_policy(material_type, identity=identity_data)),
        selected_roles=prompt_context.get("reference_role_pack") or [],
        approved_assets=approved_assets,
        passed_reference_paths=authoritative_reference_paths,
        raw_prompt=raw_prompt,
        has_base_image=bool(base_image_reference_path),
        render_backend=render_backend,
        source_url=getattr(args, "source_url", None) or "",
        entity_type=getattr(args, "entity_type", None) or "",
        selected_surface_strategy=plan.get("selected_surface_strategy") or "",
    )
    warnings.extend(policy_setup_risks)
    if render_backend == "html":
        if material_type not in {"social", "x-feed", "announcement-card"}:
            blocking_issues.append("HTML share-card backend currently supports only social, x-feed, and announcement-card materials.")
        if not (getattr(args, "source_url", None) or getattr(args, "headline", None) or getattr(args, "proof_title", None)):
            warnings.append("HTML share-card mode works best when a real source_url or explicit headline/proof fields are provided; otherwise product truth may stay generic.")
        warnings.append(
            "HTML share-card mode recreates product truth as a readable proof module. Prefer real page text/details over tiny screenshot crops or process-language labels."
        )
        if getattr(args, "proof_crop_path", None):
            warnings.append("Proof crop will be treated as supporting texture only; the readable HTML/text proof module remains primary.")

    _source_version = getattr(args, "source_version", None) or plan.get("source_version") or ""
    _branch_id = getattr(args, "branch_id", None) or plan.get("branch_id") or workflow_id
    _parent_branch_id = getattr(args, "parent_branch_id", None) or plan.get("parent_branch_id") or ""
    _selected_direction_id = (
        getattr(args, "selected_direction_id", None)
        or plan.get("selected_direction_id")
        or ((plan.get("inspiration_board") or {}).get("direction_id") or "")
    )

    payload = {
        "schema_type": "generation_scratchpad",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state": {
            "status": "blocked" if blocking_issues else "ready_to_generate",
            "owner": "visual_composer",
            "next_owner": "generator",
        },
        "brand_dir": str(brand_dir),
        "workflow_id": workflow_id,
        "source_version": _source_version,
        "branch_id": _branch_id,
        "parent_branch_id": _parent_branch_id,
        "branch_status": "active",
        "selected_direction_id": _selected_direction_id,
        "plan_path": getattr(args, "plan", None) or "",
        "plan_wrapper": plan_wrapper,
        "plan": plan,
        "inspiration_board": {
            **dict(plan.get("inspiration_board") or {}),
            "board_path": inspiration_board_path or ((plan.get("inspiration_board") or {}).get("board_path") or ""),
            "selected_inspiration_ids": selected_inspiration_ids,
        },
        "selected_reference_ids": selected_reference_ids,
        "selected_inspiration_ids": selected_inspiration_ids,
        "selected_mechanic_ids": list(plan.get("selected_mechanic_ids") or prompt_context.get("selected_mechanic_ids") or []),
        "material_type": material_type,
        "tag": tag,
        "render_backend": render_backend,
        "source_url": getattr(args, "source_url", None) or "",
        "entity_type": getattr(args, "entity_type", None) or "",
        "headline": getattr(args, "headline", None) or "",
        "subhead": getattr(args, "subhead", None) or "",
        "cta": getattr(args, "cta", None) or "",
        "proof_title": getattr(args, "proof_title", None) or "",
        "proof_excerpt": getattr(args, "proof_excerpt", None) or "",
        "proof_row": getattr(args, "proof_row", None) or "",
        "proof_meta": list(getattr(args, "proof_meta", None) or []),
        "proof_crop_path": getattr(args, "proof_crop_path", None) or "",
        "design_variance": int(getattr(args, "design_variance", None) or 5),
        "layout_spec": getattr(args, "layout_spec", None),
        "skip_proof": bool(getattr(args, "skip_proof", False)),
        "dark_mode": bool(getattr(args, "dark_mode", False)),
        "selected_surface_strategy": plan.get("selected_surface_strategy") or "",
        "selected_surface_strategy_label": plan.get("selected_surface_strategy_label") or "",
        "selected_surface_strategy_summary": plan.get("selected_surface_strategy_summary") or "",
        "selected_surface_strategy_layout_family": plan.get("selected_surface_strategy_layout_family") or "",
        "selected_surface_strategy_prompt_directive": plan.get("selected_surface_strategy_prompt_directive") or "",
        "surface_strategy_reason": plan.get("surface_strategy_reason") or "",
        "surface_strategy_candidates": list(plan.get("surface_strategy_candidates") or []),
        "source_shape": plan.get("source_shape") or "",
        "workflow_mode": workflow_mode,
        "generation_mode": generation_mode,
        "profile_path": str(profile_path),
        "identity_path": str(identity_path),
        "raw_prompt": raw_prompt,
        "prompt_context": prompt_context,
        "prompt_review": prompt_review,
        "effective_prompt": effective_prompt,
        "execution_prompt": execution_prompt,
        "reference_analysis_mode": reference_analysis_mode,
        "reference_analysis_confidence": reference_analysis_confidence,
        "policy_setup_risks": policy_setup_risks,
        "reference_context": {
            "explicit_reference_paths": [str(path) for path in reference_paths],
            "role_pack_paths": [str(path) for path in role_pack_paths],
            "role_pack_motion_paths": [str(path) for path in role_pack_motion_paths],
            "all_context_refs": [str(path) for path in all_context_refs],
            "passed_reference_paths": model_transport_reference_paths,
            "model_transport_reference_paths": model_transport_reference_paths,
            "authoritative_reference_paths": authoritative_reference_paths,
            "base_image_reference_path": str(base_image_reference_path) if base_image_reference_path else "",
            "reference_tags": reference_tag_context.get("reference_tags", []),
            "required_roles": required_roles,
            "selected_role_names": selected_role_names,
            "missing_required_roles": missing_required_roles,
            "analysis_reference_set_hash": reference_analysis.get("reference_set_hash") or "",
            "selected_reference_ids": selected_reference_ids,
            "selected_inspiration_ids": selected_inspiration_ids,
        },
        "execution": {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "resolution": getattr(args, "resolution", None),
            "duration": getattr(args, "duration", None),
            "preset": getattr(args, "preset", None),
            "negative_prompt": getattr(args, "negative_prompt", None),
            "style": getattr(args, "style", None),
            "make_gif": bool(getattr(args, "make_gif", False)),
            "base_image": getattr(args, "base_image", None) or "",
            "motion_reference": str(motion_reference) if motion_reference else "",
            "motion_mode": getattr(args, "motion_mode", None),
            "character_orientation": getattr(args, "character_orientation", None),
            "keep_original_sound": bool(getattr(args, "keep_original_sound", False)),
            "supports_reference_images": supports_reference_images,
            "reference_tags": reference_tag_context.get("reference_tags", []),
        },
        "checks": {
            "blocking": blocking_issues,
            "warnings": dedupe_keep_order(warnings + list(prompt_review.get("recommendations", []))),
        },
    }
    return payload


def apply_generation_critique_policy(
    payload: dict,
    *,
    entrypoint: str,
    critique_mode: str = "strict",
    allow_blocking: bool = False,
) -> dict:
    checks = payload.setdefault("checks", {})
    blocking = list(checks.get("blocking") or [])
    non_bypassable = [str(item) for item in blocking if _is_non_bypassable_generation_blocker(item)]
    critique_policy = build_critique_policy(
        critique_mode=critique_mode,
        entrypoint=entrypoint,
        blocking=blocking,
        allow_blocking=allow_blocking and not non_bypassable,
        bypass_reason=f"{entrypoint} ran with --allow-blocking despite blocking scratchpad findings.",
    )
    if non_bypassable:
        critique_policy["blocking_policy"] = "block_generation"
        critique_policy["blocks_generation"] = True
        critique_policy["bypass_recorded"] = False
        critique_policy["bypass_reason"] = ""
    payload["critique_policy"] = critique_policy
    state = payload.setdefault("state", {})
    if blocking and critique_policy.get("bypass_recorded"):
        state["status"] = "ready_to_generate_with_bypass"
    elif blocking:
        state["status"] = "blocked"
    else:
        state["status"] = "ready_to_generate"
    return critique_policy


def build_structural_auto_critic(payload: dict) -> dict:
    material_key = role_pack_material_key(payload.get("material_type") or "")
    review = {"p1": [], "p2": [], "p3": [], "clean": []}
    plan = payload.get("plan") or {}
    brand_policy = plan.get("brand_anchor_policy") or {}
    reference_ctx = payload.get("reference_context") or {}
    passed_refs = (
        (reference_ctx.get("authoritative_reference_paths"))
        or (reference_ctx.get("model_transport_reference_paths"))
        or (reference_ctx.get("passed_reference_paths"))
        or []
    )
    prompt_review = payload.get("prompt_review") or {}
    if material_key in INTERFACE_MATERIAL_KEYS and not passed_refs:
        review["p1"].append("Product-led material has no passed proof references; it may drift away from real product truth.")
    if brand_policy.get("logo_mode") == "required":
        profile_payload = load_json_file(Path(payload.get("profile_path") or "")) if payload.get("profile_path") else {}
        identity_payload = load_json_file(Path(payload.get("identity_path") or "")) if payload.get("identity_path") else {}
        profile_assets = (identity_payload.get("brand_assets") or profile_payload.get("brand_assets") or {})
        if not any(str(profile_assets.get(key) or "").strip() for key in ("icon", "wordmark", "lockup")):
            review["p1"].append("Logo-required material has no approved brand asset in brand memory.")
    # Proof-sensitive non-interface materials (social, landing_hero) need at least
    # one concrete subject signal — a prompt seed, product_truth_expression, or
    # passed refs.  Without any of these, the model has nothing purposeful to show
    # beyond the logo on a flat field.
    _proof_sensitive_non_interface = {"social", "landing_hero"}
    if material_key in _proof_sensitive_non_interface and not passed_refs:
        _has_prompt_seed = bool(str(plan.get("prompt_seed") or "").strip())
        _has_product_truth = bool(str(plan.get("product_truth_expression") or brand_policy.get("product_truth_expression") or "").strip())
        _has_purpose = bool(str(plan.get("purpose") or "").strip())
        if not _has_prompt_seed and not _has_product_truth:
            review["p2"].append(
                "Proof-sensitive material has no prompt seed and no product-truth expression; "
                "the model has no concrete subject to anchor on. Add --prompt-seed or "
                "--product-truth-expression to give the composition a purpose."
            )
        elif not _has_prompt_seed and not _has_purpose:
            review["p2"].append(
                "Proof-sensitive material has a product truth but no prompt seed or purpose; "
                "consider adding --prompt-seed to give the model a specific composition direction."
            )
    review["p2"].extend(prompt_review.get("issues") or [])
    review["p3"].extend((payload.get("checks") or {}).get("warnings") or [])
    if (payload.get("checks") or {}).get("blocking"):
        review["p1"].extend((payload.get("checks") or {}).get("blocking") or [])
    if not review["p1"]:
        review["clean"].append("Scratchpad passed the structural generator gate.")
    if passed_refs:
        review["clean"].append("Generation included explicit reference context.")
    return review


def run_auto_brand_review(brand_dir: Path, version_id: str) -> tuple[str, bool]:
    try:
        report, output = write_pipeline_qa_report(brand_dir, version_id)
        return str(output), bool(report)
    except Exception as exc:  # pragma: no cover - defensive fallback for generation path
        print(f"WARNING: failed to build pipeline QA report for {version_id}: {exc}", file=sys.stderr)
        return "", False


def auto_capture_generation_feedback(
    brand_dir: Path, vid: str, manifest_entry: dict, critic_summary: dict,
) -> None:
    """Auto-capture structural critic signals into iteration memory.

    Called after every generation.  Writes negative examples for P1/P2
    findings and material-specific notes for recurring P3 warnings so the
    next generation benefits from past failures via the iteration-memory
    snippet that ``build_effective_prompt`` already injects.
    """
    p1 = critic_summary.get("p1") or []
    p2 = critic_summary.get("p2") or []
    p3 = critic_summary.get("p3") or []
    if not p1 and not p2 and not p3:
        return
    try:
        memory = load_iteration_memory(brand_dir)
        if p1 or p2:
            issues = p1 + p2
            summary = "; ".join(str(i) for i in issues[:3])
            score = 1 if p1 else 2
            memory = capture_feedback_into_iteration_memory(
                memory, vid, manifest_entry,
                notes=f"Auto-critic: {summary}",
                score=score,
                status="rejected" if p1 else None,
            )
        if p3:
            material_type = manifest_entry.get("material_type") or ""
            for warning in p3[:3]:
                memory = add_iteration_note(
                    memory, f"P3: {warning}",
                    material_type=material_type,
                    bucket="material",
                )
        save_iteration_memory(brand_dir, memory)
    except Exception as exc:
        print(f"WARNING: failed to capture generation feedback for {vid}: {exc}", file=sys.stderr)


def auto_capture_vlm_feedback(
    brand_dir: Path, vid: str, manifest_entry: dict, vlm_critique: dict,
) -> None:
    """Auto-capture VLM critique signals into iteration memory.

    When the VLM critique is available, records approval as a positive
    example and P1/P2 findings as negative examples.  This closes the
    feedback loop so the prompt-assembly iteration-memory snippet reflects
    both structural and visual quality signals.
    """
    if not vlm_critique.get("vlm_available"):
        return
    try:
        memory = load_iteration_memory(brand_dir)
        vlm_p1 = vlm_critique.get("p1") or []
        vlm_p2 = vlm_critique.get("p2") or []
        approved = vlm_critique.get("approved", False)
        # Build quality detail from numeric VLM signals
        _quality_parts: list[str] = []
        _text_acc = vlm_critique.get("text_accuracy")
        if _text_acc is not None:
            _quality_parts.append(f"text_accuracy={_text_acc}")
        _palette = vlm_critique.get("palette_match")
        if _palette is not None:
            _quality_parts.append(f"palette={_palette}")
        if vlm_critique.get("hallucinated_elements"):
            _quality_parts.append(f"hallucinated={','.join(str(h) for h in vlm_critique['hallucinated_elements'][:3])}")
        _quality_tag = f" [{'; '.join(_quality_parts)}]" if _quality_parts else ""
        if vlm_p1 or vlm_p2:
            issues = vlm_p1 + vlm_p2
            summary = "; ".join(str(i) for i in issues[:3])
            score = 1 if vlm_p1 else 2
            memory = capture_feedback_into_iteration_memory(
                memory, vid, manifest_entry,
                notes=f"VLM critique: {summary}{_quality_tag}",
                score=score,
                status="rejected" if vlm_p1 else None,
            )
        elif approved:
            memory = capture_feedback_into_iteration_memory(
                memory, vid, manifest_entry,
                notes=f"VLM approved: passed visual review{_quality_tag}",
                score=4,
                status=None,
            )
        save_iteration_memory(brand_dir, memory)
    except Exception as exc:
        print(f"WARNING: failed to capture VLM feedback for {vid}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# VLM Critic + reference analysis helpers (moved to modules)
# ---------------------------------------------------------------------------


def ensure_reference_analysis(
    brand_dir: Path,
    *,
    profile: dict,
    identity: dict,
    reference_paths: list[Path],
    role_pack_roles: list[dict],
    material_type: str | None = None,
    skip_extraction: bool = False,
    refresh_extraction: bool = False,
) -> dict:
    return _ensure_reference_analysis(
        brand_dir,
        profile=profile,
        identity=identity,
        reference_paths=reference_paths,
        role_pack_roles=role_pack_roles,
        material_type=material_type,
        skip_extraction=skip_extraction,
        refresh_extraction=refresh_extraction,
        load_blackboard_fn=load_blackboard,
        save_blackboard_fn=save_blackboard,
        append_blackboard_decision_fn=append_blackboard_decision,
        summarize_identity_fn=summarize_identity,
        role_pack_material_key_fn=role_pack_material_key,
        env=build_env(),
    )


reference_analysis_review_notes = _reference_analysis_review_notes
build_reference_analysis_inputs = _build_reference_analysis_inputs
extract_reference_image_stats = _extract_reference_image_stats


def build_reference_analysis_snippet(reference_analysis: dict, material_type: str | None = None) -> str:
    return _build_reference_analysis_snippet(
        reference_analysis,
        material_type,
        role_pack_material_key_fn=role_pack_material_key,
    )


def run_vlm_critique(image_path: Path, brief: str, brand_dna: dict) -> dict:
    return _run_vlm_critique(image_path, brief, brand_dna, env=build_env())


refine_prompt_from_vlm_critique = _refine_prompt_from_vlm_critique


def check_inspiration_pipeline_status(brand_gen_dir: Path | None, active_brand: str | None, workflow_mode: str | None) -> dict:
    return _check_inspiration_pipeline_status(
        brand_gen_dir,
        active_brand,
        workflow_mode,
        resolve_active_brand_key_fn=lambda resolved: resolve_active_brand_key(brand_gen_dir=resolved, repo_root=REPO_ROOT),
    )

def execute_generation_scratchpad(payload: dict, workflow_id: str | None = None) -> str:
    if payload.get("schema_type") != "generation_scratchpad":
        raise SystemExit("Scratchpad is not a generation_scratchpad payload.")
    blocking = (((payload.get("checks") or {}).get("blocking")) or [])
    critique_policy = normalize_critique_policy(
        payload.get("critique_policy") if isinstance(payload.get("critique_policy"), dict) else payload,
        default_mode="strict",
        entrypoint="generate",
        blocking=blocking,
    )
    if blocking and critique_policy.get("blocks_generation", True):
        raise SystemExit("Generation scratchpad has blocking issues. Fix them or rebuild the scratchpad before generating.")
    if blocking:
        print("WARNING: generating with blocking critique findings because a bypass was explicitly recorded.", file=sys.stderr)

    brand_dir = validate_brand_workspace_dir(payload.get("brand_dir") or "", label="generation scratchpad brand_dir")
    payload["brand_dir"] = str(brand_dir)
    brand_dir.mkdir(parents=True, exist_ok=True)
    execution = payload.get("execution") or {}
    generation_mode = payload.get("generation_mode") or "image"
    model = execution.get("model") or ""
    model_config = MODELS.get(generation_mode, {}).get(model)
    if not model_config:
        raise SystemExit(f"Model '{model}' is not available for {generation_mode} generation.")
    ext = model_config.get("output_format", "png" if generation_mode == "image" else "mp4")
    slug = str(payload.get("tag") or payload.get("material_type") or "brand").replace(" ", "-").lower()
    execution_prompt = payload.get("execution_prompt") or payload.get("effective_prompt") or ""
    payload["execution_prompt"] = execution_prompt
    payload["effective_prompt"] = payload.get("effective_prompt") or execution_prompt
    workflow_ref = workflow_id or str(payload.get("workflow_id") or "")
    vid = _reserve_manifest_version(
        brand_dir,
        material_type=payload.get("material_type") or "",
        workflow_id=workflow_ref,
        tag=payload.get("tag") or payload.get("material_type") or "brand",
    )
    out_file = brand_dir / f"{vid}-{slug}.{ext}"
    selected_reference_ids = dedupe_keep_order(
        [
            str(item).strip()
            for item in (
                list(payload.get("selected_reference_ids") or [])
                + list(payload.get("selected_inspiration_ids") or [])
                + list(((payload.get("inspiration_board") or {}).get("selected_reference_ids") or []))
                + list(((payload.get("inspiration_board") or {}).get("selected_inspiration_ids") or []))
                + [
                    str(item.get("source_key") or item.get("path") or "").strip()
                    for item in ((payload.get("prompt_context") or {}).get("reference_role_pack") or [])
                    if str(item.get("source_key") or item.get("path") or "").strip()
                ]
            )
            if str(item).strip()
        ]
    )

    cmd = [sys.executable, str(GENERATE_PY), generation_mode, "-m", model, "-p", execution_prompt, "-o", str(out_file)]
    if execution.get("aspect_ratio"):
        cmd += ["--aspect-ratio", str(execution["aspect_ratio"])]
    if execution.get("resolution"):
        cmd += ["--resolution", str(execution["resolution"])]
    if execution.get("preset"):
        cmd += ["--preset", str(execution["preset"])]
    if execution.get("style"):
        cmd += ["--style", str(execution["style"])]
    if execution.get("negative_prompt"):
        cmd += ["--negative-prompt", str(execution["negative_prompt"])]
    if generation_mode == "video" and execution.get("duration"):
        cmd += ["--duration", str(execution["duration"])]
    if execution.get("motion_reference"):
        cmd += ["--motion-reference", str(execution["motion_reference"])]
    if execution.get("motion_mode"):
        cmd += ["--motion-mode", str(execution["motion_mode"])]
    if execution.get("character_orientation"):
        cmd += ["--character-orientation", str(execution["character_orientation"])]
    if execution.get("keep_original_sound"):
        cmd += ["--keep-original-sound"]
    # Base image support: when a base_image is specified, the model edits/overlays on it
    base_image = execution.get("base_image") or payload.get("base_image") or ""
    if base_image:
        cmd += ["--base-image", str(base_image)]
    for ref in (
        (payload.get("reference_context") or {}).get("model_transport_reference_paths")
        or (payload.get("reference_context") or {}).get("passed_reference_paths")
        or []
    ):
        cmd += ["-i", str(ref)]
    for tag in execution.get("reference_tags", []) or []:
        cmd += ["--reference-tag", tag]

    env = build_env()
    print(f"Generating {vid} ({payload.get('material_type')}, {generation_mode}, {model}, mode={payload.get('workflow_mode')})...")
    append_run_event(
        brand_dir,
        workflow_ref,
        stage="generate",
        event_type="generation_started",
        attempt_id=vid,
        material_type=payload.get("material_type") or "",
        mode=payload.get("workflow_mode") or "",
        selected_reference_paths=list((payload.get("reference_context") or {}).get("authoritative_reference_paths") or []),
        selected_reference_ids=selected_reference_ids,
        model=model,
        provider=str(model_config.get("owner") or model_config.get("provider") or ""),
        prompt=execution_prompt,
        source_version=payload.get("_previous_vid") or payload.get("source_version") or "",
        status="started",
        warnings=list((payload.get("checks") or {}).get("warnings") or []),
    )
    started_at = time.perf_counter()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        append_run_event(
            brand_dir,
            workflow_ref,
            stage="generate",
            event_type="generation_completed",
            attempt_id=vid,
            material_type=payload.get("material_type") or "",
            mode=payload.get("workflow_mode") or "",
            selected_reference_paths=list((payload.get("reference_context") or {}).get("authoritative_reference_paths") or []),
            selected_reference_ids=selected_reference_ids,
            model=model,
            provider=str(model_config.get("owner") or model_config.get("provider") or ""),
            prompt=execution_prompt,
            source_version=payload.get("_previous_vid") or payload.get("source_version") or "",
            output_version=vid,
            duration_ms=duration_ms,
            status="failed",
            notes=(result.stderr or result.stdout or "").strip()[:500],
        )
        _update_manifest_version(
            brand_dir,
            vid,
            {
                "status": "failed",
                "material_type": payload.get("material_type") or "",
                "generation_mode": generation_mode,
                "model": model,
                "mode": payload.get("workflow_mode") or "",
                "tag": payload.get("tag") or "",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "workflow_id": workflow_ref,
                "notes": (result.stderr or result.stdout or "").strip()[:500],
            },
        )
        raise SystemExit(result.returncode)

    files = [out_file.name]
    staged_sources = [Path(path) for path in ((payload.get("reference_context") or {}).get("all_context_refs") or [])]
    motion_reference = execution.get("motion_reference") or ""
    if motion_reference:
        staged_sources.append(Path(motion_reference))
    staged_refs = stage_reference_assets(vid, staged_sources, brand_dir)

    gif_file = None
    if generation_mode == "video" and (execution.get("make_gif") or payload.get("material_type") == "gif"):
        gif_file = convert_video_to_gif(out_file)
        if gif_file is not None:
            files.append(gif_file.name)

    # -- Sidecar: write heavyweight prompt fields to {vid}.prompts.json --
    sidecar_fields = {
        "prompt": execution_prompt,
        "effective_prompt": payload.get("effective_prompt") or execution_prompt,
        "execution_prompt": execution_prompt,
        "execution_prompt_kind": ((payload.get("prompt_review") or {}).get("execution_prompt_kind") or ""),
        "execution_prompt_compressed": bool((payload.get("prompt_review") or {}).get("execution_prompt_compressed")),
        "execution_prompt_sections": (payload.get("prompt_review") or {}).get("execution_prompt_sections", {}),
        "resolved_prompt": ((payload.get("prompt_review") or {}).get("resolved_prompt") or ""),
        "prompt_prelude": "\n\n".join(
            part for part in [
                ((payload.get("prompt_context") or {}).get("brand_prelude") or ""),
                ((payload.get("prompt_context") or {}).get("material_prompt_snippet") or ""),
                ((payload.get("prompt_context") or {}).get("reference_role_pack_snippet") or ""),
                ((payload.get("prompt_context") or {}).get("inspiration_doctrine") or ""),
            ] if part
        ),
        "material_prompt_snippet": (payload.get("prompt_context") or {}).get("material_prompt_snippet", ""),
        "reference_role_pack": (payload.get("prompt_context") or {}).get("reference_role_pack", []),
        "token_block": (payload.get("prompt_context") or {}).get("token_block", ""),
        "token_block_fragments": (payload.get("prompt_context") or {}).get("token_block_fragments", []),
        "prompt_review": dict(payload.get("prompt_review") or {}, scratchpad=(payload.get("prompt_review") or {}).get("scratchpad") or ""),
        "critic_summary": build_structural_auto_critic(payload),
        "critique_policy": critique_policy,
        "reference_analysis_mode": payload.get("reference_analysis_mode") or "",
        "reference_analysis_confidence": payload.get("reference_analysis_confidence") or "",
        "selected_reference_ids": selected_reference_ids,
        "selected_inspiration_ids": list(payload.get("selected_inspiration_ids") or []),
        "inspiration_board": dict(payload.get("inspiration_board") or {}),
    }
    sidecar_path = brand_dir / f"{vid}.prompts.json"
    try:
        sidecar_path.write_text(json.dumps(sidecar_fields, indent=2, default=str))
    except OSError as exc:
        print(f"WARNING: could not write sidecar {sidecar_path}: {exc}", file=sys.stderr)

    # -- Slim manifest entry (heavyweight fields moved to sidecar) --
    manifest, _ = _update_manifest_version(brand_dir, vid, {
        "prompt_char_count": len(execution_prompt),
        "raw_prompt": payload.get("raw_prompt") or "",
        "material_prompt_key": (payload.get("prompt_context") or {}).get("material_prompt_key", ""),
        "material_prompt_variant": (payload.get("prompt_context") or {}).get("material_prompt_variant", ""),
        "reference_role_pack_priority": (payload.get("prompt_context") or {}).get("reference_role_pack_priority", []),
        "reference_role_pack_prefer_unique_sources": (payload.get("prompt_context") or {}).get("reference_role_pack_prefer_unique_sources", True),
        "reference_role_pack_required_roles": (payload.get("prompt_context") or {}).get("reference_role_pack_required_roles", []),
        "reference_role_pack_missing_roles": (payload.get("prompt_context") or {}).get("reference_role_pack_missing_roles", []),
        "reference_role_pack_missing_required_roles": (payload.get("reference_context") or {}).get("missing_required_roles", []),
        "reference_tags": execution.get("reference_tags", []),
        "model": model,
        "mode": payload.get("workflow_mode") or "",
        "material_type": payload.get("material_type") or "",
        "generation_mode": generation_mode,
        "aspect_ratio": execution.get("aspect_ratio") or "",
        "duration": execution.get("duration"),
        "tag": payload.get("tag") or "",
        "files": files,
        "reference_images": staged_refs,
        "reference_count": len(staged_refs),
        "reference_dir": "",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "score": None,
        "notes": "",
        "status": None,
        "generation_scratchpad": payload.get("_scratchpad_path") or "",
        "workflow_id": workflow_ref,
        "source_version": payload.get("_previous_vid") or payload.get("source_version") or "",
        "branch_id": payload.get("branch_id") or workflow_ref,
        "parent_branch_id": payload.get("parent_branch_id") or "",
        "branch_status": payload.get("branch_status") or "active",
        "selected_direction_id": payload.get("selected_direction_id") or ((payload.get("inspiration_board") or {}).get("direction_id") or ""),
        "critic_summary": sidecar_fields["critic_summary"],
        "critique_policy": critique_policy,
        "reference_analysis_mode": payload.get("reference_analysis_mode") or "",
        "reference_analysis_confidence": payload.get("reference_analysis_confidence") or "",
        "selected_reference_ids": selected_reference_ids,
        "selected_inspiration_ids": list(payload.get("selected_inspiration_ids") or []),
    })
    append_run_event(
        brand_dir,
        workflow_ref,
        stage="generate",
        event_type="generation_completed",
        attempt_id=vid,
        material_type=payload.get("material_type") or "",
        mode=payload.get("workflow_mode") or "",
        selected_reference_paths=list((payload.get("reference_context") or {}).get("authoritative_reference_paths") or []),
        selected_reference_ids=selected_reference_ids,
        model=model,
        provider=str(model_config.get("owner") or model_config.get("provider") or ""),
        prompt=execution_prompt,
        source_version=payload.get("_previous_vid") or payload.get("source_version") or "",
        output_version=vid,
        duration_ms=duration_ms,
        status="ok",
        branch_id=payload.get("branch_id") or workflow_ref,
        parent_branch_id=payload.get("parent_branch_id") or "",
        branch_status=payload.get("branch_status") or "active",
        selected_direction_id=payload.get("selected_direction_id") or ((payload.get("inspiration_board") or {}).get("direction_id") or ""),
        data={"files": list(files), "scratchpad_path": payload.get("_scratchpad_path") or ""},
    )
    agent_review_path = ""
    agent_review_ok = False
    try:
        _, agent_review_output = write_agent_visual_review_packet(brand_dir, vid, manifest=manifest)
        agent_review_path = str(agent_review_output)
        agent_review_ok = True
    except Exception as exc:
        print(f"WARNING: failed to build agent review packet for {vid}: {exc}", file=sys.stderr)
    manifest, _ = _update_manifest_version(
        brand_dir,
        vid,
        {
            "agent_review_path": agent_review_path if agent_review_ok else "",
            "agent_review_kind": "critique_rubric" if agent_review_ok else "",
            "visual_review_status": "pending" if agent_review_ok else "",
            "visual_review_provider": "agent" if agent_review_ok else "",
        },
    )
    auto_review_path, auto_review_ok = run_auto_brand_review(brand_dir, vid)
    manifest, _ = _update_manifest_version(
        brand_dir,
        vid,
        {
            "auto_review_path": auto_review_path if auto_review_ok else "",
            "auto_review_kind": "pipeline_qa" if auto_review_ok else "",
        },
    )
    append_run_event(
        brand_dir,
        workflow_ref,
        stage="review",
        event_type="agent_review_packet_written",
        attempt_id=vid,
        material_type=payload.get("material_type") or "",
        mode=payload.get("workflow_mode") or "",
        model=model,
        output_version=vid,
        status="ok" if agent_review_ok else "failed",
        provider="agent",
        data={"agent_review_path": agent_review_path, "agent_review_kind": "critique_rubric" if agent_review_ok else ""},
    )
    append_run_event(
        brand_dir,
        workflow_ref,
        stage="review",
        event_type="pipeline_qa_written",
        attempt_id=vid,
        material_type=payload.get("material_type") or "",
        mode=payload.get("workflow_mode") or "",
        model=model,
        output_version=vid,
        status="ok" if auto_review_ok else "failed",
        data={"auto_review_path": auto_review_path, "auto_review_kind": "pipeline_qa" if auto_review_ok else ""},
    )
    profile_path = payload.get("profile_path") or None
    identity_path = payload.get("identity_path") or None
    _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
    persist_generated_asset_to_blackboard(
        brand_dir,
        profile,
        identity,
        version_id=vid,
        entry=manifest["versions"][vid],
        scratchpad_path=payload.get("_scratchpad_path") or "",
        auto_review_path=manifest["versions"][vid].get("auto_review_path") or "",
        agent_review_path=manifest["versions"][vid].get("agent_review_path") or "",
        critic_summary=manifest["versions"][vid].get("critic_summary") or {},
        workflow_id=workflow_ref,
    )
    auto_capture_generation_feedback(
        brand_dir, vid, manifest["versions"][vid], sidecar_fields["critic_summary"],
    )
    print(f"Done: {vid} -> {out_file.name}")
    try:
        generate_compare_board(brand_dir)
    except Exception:
        pass
    return vid
