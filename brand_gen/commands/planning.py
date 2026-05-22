from __future__ import annotations

from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..session_summary import *
from ..media_board import *
from ..composition_suggest import suggest_layouts, format_layout_suggestions

def cmd_critique_plan(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    wrapper, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
    workflow_id = resolve_workflow_id(wrapper, plan)
    critique_mode = getattr(args, "critique_mode", "advisory") or "advisory"
    critique = build_plan_critique_payload(
        args,
        brand_dir=brand_dir,
        wrapper=wrapper,
        plan=plan,
        critique_mode=critique_mode,
        entrypoint="critique-plan",
        allow_blocking=False,
    )
    critique["workflow_id"] = workflow_id
    report = critique["plan_validation"]
    output_path = Path(args.output).expanduser().resolve() if args.output else save_plan_critique(
        brand_dir,
        critique,
        label=f"{plan.get('material_type','material')}-{plan.get('mode','mode')}-critique",
        workflow_id=workflow_id,
    )
    if args.output:
        output_path.write_text(json.dumps(critique, indent=2) + "\n")
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    persist_plan_critique_to_blackboard(brand_dir, profile, identity, critique, output_path=output_path, workflow_id=workflow_id)
    has_blocking = bool((critique.get("checks") or {}).get("blocking"))
    critique_policy = critique.get("critique_policy") or {}
    blocks_generation = bool(critique_policy.get("blocks_generation"))
    if args.format == "json":
        print(json.dumps({**critique, "output": str(output_path)}, indent=2))
        if has_blocking and blocks_generation:
            sys.exit(1)
        return
    print(f"Plan critique: {output_path}\n")
    print(f"Status: {'ok' if report['ok'] and not critique['checks'].get('blocking') else 'needs work'}")
    print(f"Critique mode: {critique_policy.get('critique_mode') or critique_mode}")
    if report['errors']:
        print("\nPlan errors:")
        for item in report['errors']:
            print(f"- {item}")
    if report['warnings']:
        print("\nPlan warnings:")
        for item in report['warnings']:
            print(f"- {item}")
    prompt_review = critique['prompt_review']
    if prompt_review.get('issues'):
        print("\nPrompt issues:")
        for item in prompt_review['issues']:
            print(f"- {item}")
    if prompt_review.get('recommendations'):
        print("\nRecommendations:")
        for item in prompt_review['recommendations']:
            print(f"- {item}")
    if has_blocking:
        print("\nBlocking issues:")
        for item in critique['checks']['blocking']:
            print(f"- {item}")
        if blocks_generation:
            print("\n⛔ Critique has blocking issues. Fix the plan and re-run critique-plan before proceeding.")
            print("   The pipeline will not continue to build-generation-scratchpad until blocking issues are resolved.")
            sys.exit(1)
        print("\n⚠ Advisory critique recorded blocking issues, but this report does not itself block generation.")
        print("  Build-generation-scratchpad / pipeline remain strict by default unless a bypass is explicitly recorded.")

def cmd_build_generation_scratchpad(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    wrapper, plan = load_plan_payload(Path(args.plan).expanduser().resolve()) if getattr(args, "plan", None) else ({}, {})
    cli_base_image = getattr(args, "base_image", None) or ""
    plan_base_image = plan.get("base_image") or ""
    effective_base_image = cli_base_image or plan_base_image
    if effective_base_image:
        effective_base_image_path = Path(effective_base_image).expanduser().resolve()
        if not effective_base_image_path.is_file():
            raise SystemExit(f"ERROR: --base-image path does not exist: {effective_base_image_path}")
        args.base_image = str(effective_base_image_path)
    workflow_id = resolve_workflow_id(wrapper, plan)
    payload = assemble_generation_scratchpad(args, brand_dir=brand_dir, plan_wrapper=wrapper, plan=plan)
    payload["workflow_id"] = workflow_id
    critique_mode = getattr(args, "critique_mode", "strict") or "strict"
    critique = (
        build_plan_critique_payload(
            args,
            brand_dir=brand_dir,
            wrapper=wrapper,
            plan=plan,
            critique_mode=critique_mode,
            entrypoint="build-generation-scratchpad",
            allow_blocking=bool(getattr(args, "allow_blocking", False)),
        )
        if plan
        else {}
    )
    if critique:
        critique["workflow_id"] = workflow_id
    payload["plan_critique"] = critique
    if critique:
        payload["checks"]["blocking"] = dedupe_keep_order(list(payload["checks"].get("blocking") or []) + list((critique.get("checks") or {}).get("blocking") or []))
        payload["checks"]["warnings"] = dedupe_keep_order(list(payload["checks"].get("warnings") or []) + list((critique.get("checks") or {}).get("warnings") or []))
    apply_generation_critique_policy(
        payload,
        entrypoint="build-generation-scratchpad",
        critique_mode=critique_mode,
        allow_blocking=bool(getattr(args, "allow_blocking", False)),
    )
    output_path = Path(args.output).expanduser().resolve() if args.output else save_generation_scratchpad(
        brand_dir,
        payload,
        label=f"{payload.get('material_type','material')}-{payload.get('workflow_mode','mode')}-generation",
        workflow_id=workflow_id,
    )
    if args.output:
        output_path.write_text(json.dumps(payload, indent=2) + "\n")
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    persist_generation_scratchpad_to_blackboard(brand_dir, profile, identity, payload, output_path=output_path, workflow_id=workflow_id)
    if args.format == "json":
        print(json.dumps({**payload, "output": str(output_path)}, indent=2))
    else:
        print(f"Generation scratchpad: {output_path}\n")
        print(f"Material: {payload.get('material_type')}\nModel: {(payload.get('execution') or {}).get('model')}\nMode: {payload.get('workflow_mode')}")
        if (payload.get('checks') or {}).get('blocking'):
            print("\nBlocking issues:")
            for item in (payload.get('checks') or {}).get('blocking') or []:
                print(f"- {item}")
        if (payload.get('checks') or {}).get('warnings'):
            print("\nWarnings:")
            for item in (payload.get('checks') or {}).get('warnings') or []:
                print(f"- {item}")
    critique_policy = payload.get("critique_policy") or {}
    if (payload.get('checks') or {}).get('blocking') and critique_policy.get("blocks_generation", True):
        sys.exit(1)

def cmd_reference_rubric(args):
    """Return reference image paths + analysis rubric for the calling agent."""
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))

    reference_paths = list(brand_dir.joinpath("references").glob("*")) if brand_dir.joinpath("references").exists() else []
    reference_paths = [p for p in reference_paths if p.suffix.lower() in SUPPORTED_IMAGE_EXTS]

    if not reference_paths:
        print(json.dumps({"error": "No reference images found in references/ directory"}))
        return

    summary = summarize_identity(profile, identity)
    brand_context = (
        f"Brand: {summary.get('brand_name') or 'n/a'}\n"
        f"Summary: {summary.get('summary') or 'n/a'}\n"
        f"Palette direction: {', '.join(summary.get('palette_direction') or []) or 'n/a'}\n"
        f"Typography roles: {', '.join(f'{v} ({k})' for k, v in (summary.get('typography_roles') or {}).items()) or 'n/a'}\n"
        f"Approved devices: {', '.join(summary.get('approved_graphic_devices') or []) or 'n/a'}"
    )

    images = []
    for p in reference_paths[:8]:
        images.append({
            "path": str(p),
            "filename": p.name,
        })

    rubric = {
        "reference_images": images,
        "brand_context": brand_context,
        "rubric": {
            "instructions": (
                "Look at each reference image and analyze it in the context of the brand. "
                "For product-truth images, extract actual palette, typography, component cues. "
                "For inspiration images, extract transferable mechanics (composition, spacing, texture). "
                "Return a JSON object with key 'analyses' containing a list. Each item should have:"
            ),
            "per_image_schema": {
                "path": "string — the image path (echo it back)",
                "composition": "string — brief composition assessment",
                "lighting_style": "string — lighting quality",
                "typography_cues": "list of observed typography characteristics",
                "texture_patterns": "list of textures or patterns observed",
                "mood_keywords": "list of mood/atmosphere words",
                "notable_elements": "list of notable visual elements",
                "transferable_mechanics": "list of design mechanics that could transfer to brand materials",
                "role_relevance": "string — how relevant this image is: high/medium/low",
                "confidence": "float 0-1 — confidence in the analysis",
            },
        },
    }
    print(json.dumps(rubric, indent=2))


def cmd_submit_reference_analysis(args):
    """Accept agent-provided reference analysis JSON."""
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))

    analysis_path = Path(args.analysis_json).expanduser().resolve()
    if not analysis_path.exists():
        print(json.dumps({"error": f"Analysis file not found: {analysis_path}"}))
        sys.exit(1)

    agent_data = json.loads(analysis_path.read_text())
    analyses = agent_data.get("analyses") or []

    # Convert agent analyses into the internal format
    reference_inputs = []
    for item in analyses:
        reference_inputs.append({
            "path": item.get("path") or "",
            "role": "reference",
            "bucket": "product" if "product" in (item.get("role_relevance") or "").lower() else "inspiration",
        })

    # Build aggregated analysis from agent data
    all_mechanics = []
    all_mood = []
    all_typography = []
    all_notable = []
    for item in analyses:
        all_mechanics.extend(item.get("transferable_mechanics") or [])
        all_mood.extend(item.get("mood_keywords") or [])
        all_typography.extend(item.get("typography_cues") or [])
        all_notable.extend(item.get("notable_elements") or [])

    aggregated = {
        "schema_version": REFERENCE_ANALYSIS_VERSION,
        "reference_set_hash": hashlib.sha256(json.dumps(analyses, sort_keys=True).encode()).hexdigest()[:20],
        "analyses": analyses,
        "transferable_mechanics": dedupe_keep_order([str(m).strip() for m in all_mechanics if str(m).strip()])[:10],
        "mood_keywords": dedupe_keep_order([str(m).strip() for m in all_mood if str(m).strip()])[:8],
        "typography_cues": dedupe_keep_order([str(t).strip() for t in all_typography if str(t).strip()])[:6],
        "notable_elements": dedupe_keep_order([str(n).strip() for n in all_notable if str(n).strip()])[:10],
        "consistency_score": 0.7,
        "warnings": [],
        "vlm_provider": "agent",
    }

    # Save to blackboard
    board = load_blackboard(brand_dir, profile, identity)
    board["reference_analysis"] = aggregated
    append_blackboard_decision(
        board,
        agent="critic_agent",
        decision=f"Agent provided reference analysis for {len(analyses)} images.",
        confidence=0.85,
        data={"image_count": len(analyses)},
    )
    save_blackboard(brand_dir, board)

    print(json.dumps({
        "status": "saved",
        "image_count": len(analyses),
        "transferable_mechanics": aggregated["transferable_mechanics"][:5],
    }, indent=2))

def cmd_improvement_questions(args):
    """Surface contextual questions the agent should ask to improve brand understanding."""
    brand_dir = get_brand_dir()
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    manifest = load_manifest()
    
    questions = build_improvement_questions(brand_dir, profile, identity, manifest)
    freshness = check_identity_freshness(brand_dir, manifest, identity)
    
    limit = getattr(args, "limit", 3) or 3
    questions = questions[:limit]
    
    payload = {
        "questions": questions,
        "identity_freshness": freshness,
        "total_questions_available": len(build_improvement_questions(brand_dir, profile, identity, manifest)),
    }
    
    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        return
    
    if freshness["needs_rebuild"]:
        print("⚠ IDENTITY REBUILD RECOMMENDED:")
        for reason in freshness["reasons"]:
            print(f"  → {reason}")
        print()
    
    if not questions:
        print("No improvement questions at this stage. Keep generating!")
        return
    
    print(f"Improvement questions ({len(questions)}):\n")
    for i, q in enumerate(questions, 1):
        print(f"{i}. [{q['category']}] (priority {q['priority']}/5)")
        print(f"   {q['question']}")
        print(f"   Context: {q['context']}")
        print()

def cmd_route_request(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    payload = build_route_payload(args, brand_dir, profile, identity)
    board = load_blackboard(brand_dir, profile, identity)
    append_blackboard_decision(
        board,
        agent="brand_director",
        decision=f"Routed request for {payload.get('material_type') or 'brand material'} to {payload.get('route_label')}.",
        confidence=float(payload.get("score") or 0.0),
        data={
            "route_key": payload.get("route_key"),
            "goal": payload.get("goal"),
            "request": payload.get("request"),
            "score_vector": payload.get("score_vector") or {},
            "method": payload.get("method") or "default",
        },
    )
    save_blackboard(brand_dir, board)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print("Workflow route\n")
    print(f"Material: {payload.get('material_type') or 'n/a'}")
    print(f"Route: {payload.get('route_label')}")
    print(f"Specialists: {', '.join(payload.get('specialists') or []) or 'n/a'}")
    print(f"Plan first: {'yes' if payload.get('should_plan_first') else 'no'}")
    if payload.get("required_assets"):
        print(f"Required assets: {', '.join(payload['required_assets'])}")
    if payload.get("required_questions"):
        print("Questions:")
        for item in payload["required_questions"]:
            print(f"- {item}")
    if payload.get("next_commands"):
        print("Next commands:")
        for item in payload["next_commands"]:
            print(f"- {item}")
    if payload.get("notes"):
        print(f"Notes: {payload['notes']}")


def cmd_resolve_prompt(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
    )
    role_pack_override = None
    plan = None
    if getattr(args, "plan", None):
        _, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
        role_pack_override = build_role_pack_override_from_plan(plan)
    raw_prompt = args.prompt or (plan.get("prompt_seed") if plan else "") or ""
    if not raw_prompt.strip():
        print("ERROR: resolve-prompt requires --prompt or --plan with a prompt_seed.", file=sys.stderr)
        sys.exit(1)
    board = load_blackboard(brand_dir, profile, identity)
    reference_analysis = board.get("reference_analysis") or {}
    if getattr(args, "refresh_reference_analysis", False):
        role_pack_roles = (role_pack_override or {}).get("roles") or []
        ref_paths = [Path(item["path"]).expanduser().resolve() for item in role_pack_roles if item.get("path")]
        reference_analysis = ensure_reference_analysis(
            brand_dir,
            profile=profile,
            identity=identity,
            reference_paths=ref_paths,
            role_pack_roles=role_pack_roles,
            material_type=args.material_type or (plan.get("material_type") if plan else None),
            refresh_extraction=True,
        )
    context = build_effective_prompt(
        profile,
        identity,
        raw_prompt,
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        brand_dir=brand_dir,
        material_type=args.material_type or (plan.get("material_type") if plan else None),
        workflow_mode=args.mode if args.mode != "auto" else (plan.get("mode") if plan else "auto"),
        disable_brand_guardrails=args.disable_brand_guardrails,
        role_pack_override=role_pack_override,
        reference_analysis=reference_analysis,
        selected_inspiration_sources=list((plan or {}).get("selected_inspiration_sources") or []),
        selected_inspiration_ids=list((plan or {}).get("selected_inspiration_ids") or []),
        selected_mechanic_ids=list((plan or {}).get("selected_mechanic_ids") or []),
        selected_mechanic_labels=list((plan or {}).get("selected_mechanic_labels") or []),
        inspiration_selection_reason=str((plan or {}).get("inspiration_selection_reason") or ""),
        inspiration_selection_mode=str((plan or {}).get("inspiration_selection_mode") or ""),
    )
    resolved = context["resolved_prompt"]
    if args.format == "json":
        print(json.dumps({
            "profile": str(profile_path),
            "identity": str(identity_path),
            "brand_prelude": context["brand_prelude"],
            "iteration_memory_snippet": context.get("iteration_memory_snippet", ""),
            "blackboard_learning_snippet": context.get("blackboard_learning_snippet", ""),
            "blackboard_learning_summary": context.get("blackboard_learning_summary", {}),
            "material_prompt_key": context["material_prompt_key"],
            "material_prompt_variant": context["material_prompt_variant"],
            "material_prompt_snippet": context["material_prompt_snippet"],
            "reference_role_pack": context["reference_role_pack"],
            "reference_role_pack_priority": context["reference_role_pack_priority"],
            "reference_role_pack_prefer_unique_sources": context["reference_role_pack_prefer_unique_sources"],
            "reference_role_pack_paths": context["reference_role_pack_paths"],
            "reference_role_pack_motion_paths": context["reference_role_pack_motion_paths"],
            "reference_role_pack_snippet": context["reference_role_pack_snippet"],
            "reference_role_pack_required_roles": context["reference_role_pack_required_roles"],
            "reference_role_pack_missing_roles": context["reference_role_pack_missing_roles"],
            "reference_role_pack_missing_required_roles": context["reference_role_pack_missing_required_roles"],
            "reference_role_assignment_warnings": context.get("reference_role_assignment_warnings", []),
            "policy_setup_risks": context.get("policy_setup_risks", []),
            "reference_analysis": context.get("reference_analysis", {}),
            "reference_analysis_mode": context.get("reference_analysis_mode", ""),
            "reference_analysis_confidence": context.get("reference_analysis_confidence", ""),
            "reference_analysis_warning": context.get("reference_analysis_warning", ""),
            "reference_analysis_snippet": context.get("reference_analysis_snippet", ""),
            "inspiration_doctrine": context["inspiration_doctrine"],
            "selected_inspiration_translation": context.get("selected_inspiration_translation", ""),
            "selected_inspiration_ids": context.get("selected_inspiration_ids", []),
            "selected_mechanic_ids": context.get("selected_mechanic_ids", []),
            "inspiration_selection_reason": context.get("inspiration_selection_reason", ""),
            "inspiration_selection_mode": context.get("inspiration_selection_mode", ""),
            "token_block": context["token_block"],
            "token_block_fragments": context.get("token_block_fragments", []),
            "inspiration_sources": context["inspiration_sources"],
            "skipped_inspiration_sources": context["skipped_inspiration_sources"],
            "raw_prompt": raw_prompt,
            "resolved_prompt": resolved,
        }, indent=2))
        return

    print("Resolved prompt\n")
    if context["brand_prelude"]:
        print(f"Prelude source profile: {profile_path}")
        print(f"Prelude source identity: {identity_path}")
        print("\nBrand prelude:\n")
        print(context["brand_prelude"])
    if context.get("iteration_memory_snippet"):
        print("\nIteration memory:\n")
        print(context["iteration_memory_snippet"])
    if context.get("blackboard_learning_snippet"):
        print("\nBlackboard learning:\n")
        print(context["blackboard_learning_snippet"])
    if context["material_prompt_snippet"]:
        variant = f"/{context['material_prompt_variant']}" if context["material_prompt_variant"] else ""
        print(f"\nMaterial doctrine snippet ({context['material_prompt_key']}{variant}):\n")
        print(context["material_prompt_snippet"])
    if context["reference_role_pack_snippet"]:
        print("\nReference role pack:\n")
        print(context["reference_role_pack_snippet"])
    if context.get("reference_role_assignment_warnings"):
        print("\nReference-role assignment warnings:")
        for item in context["reference_role_assignment_warnings"]:
            print(f"- {item}")
    if context.get("policy_setup_risks"):
        print("\nPolicy/setup risks:")
        for item in context["policy_setup_risks"]:
            print(f"- {item}")
    if context.get("reference_analysis_snippet"):
        print("\nReference analysis:\n")
        print(context["reference_analysis_snippet"])
    if context.get("reference_analysis_mode"):
        print(f"\nReference-analysis mode: {context['reference_analysis_mode']}")
        print(f"Reference-analysis confidence: {context.get('reference_analysis_confidence') or 'low'}")
    if context.get("reference_analysis_warning"):
        print(f"Reference-analysis warning: {context['reference_analysis_warning']}")
    if context["inspiration_doctrine"]:
        print("\nInspiration doctrine:\n")
        print(context["inspiration_doctrine"])
        if context["inspiration_sources"]:
            print(f"\nSources: {', '.join(context['inspiration_sources'])}")
    if context.get("selected_inspiration_translation"):
        print("\nSelected inspiration translation:\n")
        print(context["selected_inspiration_translation"])
        if context.get("selected_inspiration_ids"):
            print(f"\nSelected inspiration IDs: {', '.join(context['selected_inspiration_ids'])}")
    if context["token_block"]:
        print("\nToken block:\n")
        print(context["token_block"])
    if not (context["brand_prelude"] or context["inspiration_doctrine"] or context["token_block"]):
        print("No brand guardrail prelude or inspiration doctrine found.\n")
    print("\nResolved prompt:\n")
    print(resolved)


def cmd_review_prompt(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    brand_gen_dir = get_brand_gen_dir()
    active_brand = resolve_context_brand_key(
        brand_dir=brand_dir,
        profile_path=profile_path,
        identity_path=identity_path,
        profile=profile,
        identity=identity,
        brand_gen_dir=brand_gen_dir,
    )
    role_pack_override = None
    plan = None
    if getattr(args, "plan", None):
        _, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
        role_pack_override = build_role_pack_override_from_plan(plan)
    raw_prompt = args.prompt or (plan.get("prompt_seed") if plan else "") or ""
    if not raw_prompt.strip():
        print("ERROR: review-prompt requires --prompt or --plan with a prompt_seed.", file=sys.stderr)
        sys.exit(1)
    material_type = args.material_type or (plan.get("material_type") if plan else None)
    workflow_mode = args.mode if args.mode != "auto" else (plan.get("mode") if plan else "auto")
    board = load_blackboard(brand_dir, profile, identity)
    reference_analysis = board.get("reference_analysis") or {}
    if getattr(args, "refresh_reference_analysis", False):
        role_pack_roles = (role_pack_override or {}).get("roles") or []
        ref_paths = [Path(item["path"]).expanduser().resolve() for item in role_pack_roles if item.get("path")]
        reference_analysis = ensure_reference_analysis(
            brand_dir,
            profile=profile,
            identity=identity,
            reference_paths=ref_paths,
            role_pack_roles=role_pack_roles,
            material_type=material_type,
            refresh_extraction=True,
        )
    context = build_effective_prompt(
        profile,
        identity,
        raw_prompt,
        brand_gen_dir=brand_gen_dir,
        active_brand=active_brand,
        brand_dir=brand_dir,
        material_type=material_type,
        workflow_mode=workflow_mode,
        disable_brand_guardrails=args.disable_brand_guardrails,
        role_pack_override=role_pack_override,
        reference_analysis=reference_analysis,
        selected_inspiration_sources=list((plan or {}).get("selected_inspiration_sources") or []),
        selected_inspiration_ids=list((plan or {}).get("selected_inspiration_ids") or []),
        selected_mechanic_ids=list((plan or {}).get("selected_mechanic_ids") or []),
        selected_mechanic_labels=list((plan or {}).get("selected_mechanic_labels") or []),
        inspiration_selection_reason=str((plan or {}).get("inspiration_selection_reason") or ""),
        inspiration_selection_mode=str((plan or {}).get("inspiration_selection_mode") or ""),
    )
    review = review_prompt_architecture(
        profile,
        identity,
        raw_prompt,
        context,
        material_type=material_type,
        workflow_mode=workflow_mode,
        token_block=context.get("token_block", ""),
        generation_mode=resolve_generation_mode(material_type, "auto"),
    )
    scratchpad = save_prompt_review_scratchpad(
        brand_dir,
        {
            "profile": str(profile_path),
            "identity": str(identity_path),
            "material_type": material_type,
            "mode": workflow_mode,
            **review,
        },
        label=f"{material_type or 'material'}-{workflow_mode or 'mode'}-review",
    )
    if args.format == "json":
        print(json.dumps({
            "profile": str(profile_path),
            "identity": str(identity_path),
            "material_type": material_type,
            "mode": workflow_mode,
            "scratchpad": str(scratchpad),
            "reference_analysis_mode": review.get("reference_analysis_mode") or "",
            "reference_analysis_confidence": review.get("reference_analysis_confidence") or "",
            "reference_analysis_warning": review.get("reference_analysis_warning") or "",
            "reference_role_assignment_warnings": review.get("reference_role_assignment_warnings") or [],
            "policy_setup_risks": review.get("policy_setup_risks") or [],
            **review,
        }, indent=2))
        return

    print("Prompt review\n")
    print(f"Material: {material_type or 'n/a'}")
    print(f"Mode: {workflow_mode}")
    if review.get("reference_analysis_mode"):
        print(f"Reference-analysis mode: {review['reference_analysis_mode']}")
        print(f"Reference-analysis confidence: {review.get('reference_analysis_confidence') or 'low'}")
    if review.get("reference_analysis_warning"):
        print(f"Reference-analysis warning: {review['reference_analysis_warning']}")
    if review["issues"]:
        print("\nIssues:")
        for item in review["issues"]:
            print(f"- {item}")
    if review["recommendations"]:
        print("\nRecommendations:")
        for item in review["recommendations"]:
            print(f"- {item}")
    if review["compact_role_pack"]:
        print("\nReference translation summary:\n")
        print(review["compact_role_pack"])
    if review.get("selected_inspiration_translation"):
        print("\nSelected inspiration translation:\n")
        print(review["selected_inspiration_translation"])
    if review.get("reference_role_assignment_warnings"):
        print("\nReference-role assignment warnings:")
        for item in review["reference_role_assignment_warnings"]:
            print(f"- {item}")
    if review.get("policy_setup_risks"):
        print("\nPolicy/setup risks:")
        for item in review["policy_setup_risks"]:
            print(f"- {item}")
    print(f"\nScratchpad: {scratchpad}")
    print("\nRefined prompt:\n")
    print(review["refined_prompt"])
    if review.get("execution_prompt"):
        print(f"\nExecution prompt ({review.get('execution_prompt_kind') or 'default'}):\n")
        print(review["execution_prompt"])


def cmd_suggest_role_pack(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    candidates = suggest_reference_role_pack(brand_dir, args.material_type)
    if args.format == "json":
        print(json.dumps(candidates, indent=2))
        return
    print(f"Reference-role suggestions for {args.material_type}\n")
    print(f"Material key: {candidates.get('material_key') or 'n/a'}")
    print(f"Priority: {', '.join(candidates.get('priority') or []) or 'n/a'}")
    print(f"Required: {', '.join(candidates.get('required_roles') or []) or 'n/a'}")
    print(f"Prefer unique sources: {'yes' if candidates.get('prefer_unique_sources', True) else 'no'}")
    if candidates.get("selection_note"):
        print(f"Selection note: {candidates['selection_note']}")
    for role in candidates.get("priority") or []:
        print(f"\n[{role}]")
        for item in (candidates.get("candidates", {}).get(role) or [])[: args.top]:
            suffix_bits = []
            if item.get("used_role_asset"):
                suffix_bits.append("role-asset")
            if item.get("translation_only"):
                suffix_bits.append("translation-only")
            if item.get("direct_generation_risk"):
                suffix_bits.append(f"risk={item['direct_generation_risk']}")
            suffix = f" {' '.join(suffix_bits)}" if suffix_bits else ""
            print(f"- {item['source_key']}: {item['source_name']} ({Path(item['path']).name}, {item['asset_kind']}{suffix})")
            if item.get("notes"):
                print(f"  {item['notes']}")
            translation = default_reference_translation(role, item)
            if translation.get("summary"):
                print(f"  translate: {translation['summary']}")


def cmd_suggest_layout(args):
    """Suggest composition layouts from the vocabulary for a material type."""
    suggestions = suggest_layouts(args.material_type, count=getattr(args, "count", 4) or 4)
    if getattr(args, "format", "text") == "json":
        print(json.dumps({"material_type": args.material_type, "suggestions": suggestions}, indent=2))
        return
    print(f"Layout suggestions for {args.material_type}\n")
    print(format_layout_suggestions(suggestions))


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

def cmd_plan_material(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, plan, missing_required = build_material_plan_from_args(args, brand_dir)
    plans_dir = brand_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output).expanduser().resolve() if args.output else plans_dir / f"{slugify(plan['material_type'])}-{slugify(args.mode)}-plan.json"
    output_path.write_text(json.dumps(plan, indent=2) + "\n")
    if args.format == "json":
        print(json.dumps(plan, indent=2))
        return
    print(f"Material plan written to: {output_path}\n")
    print(f"Material: {plan['material_type']}")
    resolution = plan.get("material_type_resolution") or {}
    if resolution.get("changed"):
        print(f"Requested material: {resolution.get('requested')} → planned as {resolution.get('resolved')}")
        if resolution.get("note"):
            print(f"Material note: {resolution.get('note')}")
    print(f"Mode: {plan['mode']}")
    print(f"Purpose: {plan.get('purpose') or 'n/a'}")
    print(f"Surface: {plan.get('target_surface') or 'n/a'}")
    print(f"Product truth: {plan.get('product_truth_expression') or 'n/a'}")
    print(f"Surface strategy: {plan.get('selected_surface_strategy_label') or plan.get('selected_surface_strategy') or 'n/a'}")
    print(f"Branding rule: {(plan.get('brand_anchor_policy') or {}).get('rule') or 'n/a'}")
    print(f"Mechanic: {plan['system_mechanic'] or 'n/a'}")
    print(f"Preserve: {', '.join(plan['preserve']) or 'n/a'}")
    print(f"Push: {', '.join(plan['push']) or 'n/a'}")
    print(f"Ban: {', '.join(plan['ban']) or 'n/a'}")
    print("\nSelected roles:")
    for item in ((plan.get("role_pack") or {}).get("selected_roles") or []):
        print(f"- {item['role']}: {item['source_key']} ({Path(item['path']).name})")
        translation = (item.get("translation") or {}).get("summary")
        if translation:
            print(f"  translate: {translation}")
    if missing_required:
        print(f"\nMissing required roles: {', '.join(missing_required)}")
    print("\nPrompt seed:\n")
    print(plan["prompt_seed"])


def cmd_plan_draft(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    base_image = getattr(args, "base_image", None) or ""
    if base_image:
        base_image_path = Path(base_image).expanduser().resolve()
        if not base_image_path.is_file():
            raise SystemExit(f"ERROR: --base-image path does not exist: {base_image_path}")
        base_image = str(base_image_path)
    _, plan, missing_required = build_material_plan_from_args(args, brand_dir)
    if base_image:
        plan["base_image"] = base_image
    selected_role_names = [str(item.get("role") or "").strip() for item in ((plan.get("role_pack") or {}).get("selected_roles") or []) if str(item.get("role") or "").strip()]
    workflow_id = resolve_workflow_id(plan)
    draft = {
        "schema_type": "plan_draft",
        "schema_version": 1,
        "workflow_id": workflow_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "state": {
            "status": "drafted",
            "owner": "brand_director",
            "next_owner": "critic_agent",
        },
        "plan": plan,
        "derived": {
            "selected_role_names": selected_role_names,
            "missing_required_roles": missing_required,
        },
        "next_step": "Run critique-plan on this draft before building a generation scratchpad.",
    }
    output_path = Path(args.output).expanduser().resolve() if args.output else save_plan_draft(
        brand_dir,
        draft,
        label=f"{plan['material_type']}-{args.mode}-plan-draft",
        workflow_id=workflow_id,
    )
    if args.output:
        output_path.write_text(json.dumps(draft, indent=2) + "\n")
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    persist_plan_draft_to_blackboard(brand_dir, profile, identity, draft, output_path=output_path, workflow_id=workflow_id)
    _record_plan_archetype_rotation(brand_dir, plan)
    if args.format == "json":
        print(json.dumps({**draft, "output": str(output_path)}, indent=2))
        return
    print(f"Plan draft written to: {output_path}\n")
    print(f"Material: {plan['material_type']}")
    resolution = plan.get("material_type_resolution") or {}
    if resolution.get("changed"):
        print(f"Requested material: {resolution.get('requested')} → planned as {resolution.get('resolved')}")
    print(f"Mode: {plan['mode']}")
    print(f"Mechanic: {plan['system_mechanic'] or 'n/a'}")
    print(f"Surface strategy: {plan.get('selected_surface_strategy_label') or plan.get('selected_surface_strategy') or 'n/a'}")
    print(f"Missing required roles: {', '.join(missing_required) or 'none'}")
    print("\nNext step:")
    print(draft["next_step"])

def _record_plan_archetype_rotation(brand_dir: Path, plan: dict) -> None:
    material_type = str(plan.get("material_type") or "").strip()
    archetype_id = str(plan.get("aesthetic_archetype_id") or "").strip()
    framing_id = str(((plan.get("sage_framing_direction") or {}).get("id") if isinstance(plan.get("sage_framing_direction"), dict) else "") or "").strip()
    if not material_type or (not archetype_id and not framing_id):
        return
    try:
        from ..aesthetic_archetypes import list_archetypes, record_archetype_choice
        from ..iteration_memory import load_iteration_memory, record_sage_framing_choice, save_iteration_memory
        from ..sage_generation_contract import SAGE_FRAMING_DIRECTIONS

        memory = load_iteration_memory(brand_dir)
        if archetype_id:
            memory = record_archetype_choice(
                memory,
                material_type=material_type,
                archetype_id=archetype_id,
                archetype_set_size=len(list_archetypes(material_type)) or None,
            )
        if framing_id:
            memory = record_sage_framing_choice(
                memory,
                material_type=material_type,
                framing_id=framing_id,
                framing_set_size=len(SAGE_FRAMING_DIRECTIONS),
            )
        save_iteration_memory(brand_dir, memory)
    except Exception as exc:
        warn(f"failed to record aesthetic archetype rotation: {exc}")


def cmd_ideate_material(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    candidates = suggest_reference_role_pack(brand_dir, args.material_type)
    tracks = default_idea_tracks(args.material_type)
    questions = default_alignment_questions(args.material_type)
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "the brand").strip()
    for track in tracks:
        recommended_roles = {}
        for role in (candidates.get("priority") or []):
            items = candidates.get("candidates", {}).get(role) or []
            if items:
                recommended_roles[role] = items[0]["source_key"]
        track["recommended_roles"] = recommended_roles
        if args.goal:
            track["why"] = f"{track['why']} This is especially relevant if the goal is: {args.goal}."
    out = {
        "brand": brand_name,
        "material_type": args.material_type,
        "mode": args.mode,
        "goal": args.goal or "",
        "use_surface": args.use_surface or "",
        "concern": args.concern or "",
        "tracks": tracks,
        "alignment_questions": questions,
        "next_step": f"Pick one track, then run: plan-material --material-type {args.material_type} --mode {args.mode} --mechanic \"<chosen mechanic>\" ...",
    }
    if args.format == "json":
        print(json.dumps(out, indent=2))
        return
    print(f"{brand_name} {args.material_type} ideation\n")
    if args.goal:
        print(f"Goal: {args.goal}")
    if args.use_surface:
        print(f"Surface: {args.use_surface}")
    if args.concern:
        print(f"Concern: {args.concern}")
    print("")
    for idx, track in enumerate(tracks, 1):
        print(f"{idx}. {track['name']}")
        print(f"   mechanic: {track['mechanic']}")
        print(f"   why: {track['why']}")
        print(f"   preserve: {', '.join(track['preserve'])}")
        print(f"   push: {', '.join(track['push'])}")
        print(f"   ban: {', '.join(track['ban'])}")
        if track.get("recommended_roles"):
            print(f"   refs: {', '.join(f'{k}={v}' for k, v in track['recommended_roles'].items())}")
        print("")
    print("Alignment questions:")
    for item in questions:
        print(f"- {item}")
    print(f"\nNext step:\n{out['next_step']}")


def cmd_ideate_copy(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    payload = derive_copy_candidates(profile, identity, args.material_type, goal=args.goal or "", surface=args.surface or "", brand_dir=brand_dir)
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return
    print(f"{payload['brand_name']} copy ideation — {payload['material_type']}\n")
    if payload["goal"]:
        print(f"Goal: {payload['goal']}")
    if payload["surface"]:
        print(f"Surface: {payload['surface']}")
    messaging = payload.get("messaging") or {}
    if messaging.get("tagline") or messaging.get("elevator"):
        print("\nMessaging context:")
        if messaging.get("tagline"):
            print(f"- Tagline: {messaging['tagline']}")
        if messaging.get("elevator"):
            print(f"- Elevator: {messaging['elevator']}")
        if messaging.get("iteration_notes"):
            print("- Messaging notes:")
            for item in messaging["iteration_notes"]:
                print(f"  - {item}")
    print("\nHeadline candidates:")
    for item in payload["headlines"]:
        print(f"- {item}")
    print("\nSlogan candidates:")
    for item in payload["slogans"]:
        print(f"- {item}")
    print("\nSubheadline candidates:")
    for item in payload["subheadlines"]:
        print(f"- {item}")
    print("\nCTA pairs:")
    for item in payload["cta_pairs"]:
        print(f"- {item['primary']} / {item['secondary']}")
    print("\nVisual angles:")
    for item in payload["visual_angles"]:
        print(f"- {item}")
    print("\nAvoid:")
    for item in payload["anti_patterns"]:
        print(f"- {item}")


def cmd_update_messaging(args):
    """Update the messaging section of the active brand identity."""
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    messaging = identity.get("messaging") or {}
    copy_bank = messaging.get("approved_copy_bank") or {}
    changed = False

    if args.tagline:
        messaging["tagline"] = args.tagline.strip()
        changed = True
    if args.elevator:
        messaging["elevator"] = args.elevator.strip()
        changed = True
    if args.voice_description:
        voice = messaging.get("voice") or {}
        voice["description"] = args.voice_description.strip()
        messaging["voice"] = voice
        changed = True
    if args.add_value_prop:
        props = messaging.get("value_propositions") or []
        for prop in args.add_value_prop:
            prop = prop.strip()
            if prop and prop not in props:
                props.append(prop)
        messaging["value_propositions"] = props
        changed = True
    if args.add_headline:
        headlines = copy_bank.get("headlines") or []
        for h in args.add_headline:
            h = h.strip()
            if h and h not in headlines:
                headlines.append(h)
        copy_bank["headlines"] = headlines
        changed = True
    if args.add_slogan:
        slogans = copy_bank.get("slogans") or []
        for s in args.add_slogan:
            s = s.strip()
            if s and s not in slogans:
                slogans.append(s)
        copy_bank["slogans"] = slogans
        changed = True
    if args.add_subheadline:
        subs = copy_bank.get("subheadlines") or []
        for s in args.add_subheadline:
            s = s.strip()
            if s and s not in subs:
                subs.append(s)
        copy_bank["subheadlines"] = subs
        changed = True

    if not changed:
        print("No messaging updates provided. Use --tagline, --elevator, --add-headline, etc.")
        return

    messaging["approved_copy_bank"] = copy_bank
    identity["messaging"] = messaging
    identity["schema_version"] = max(identity.get("schema_version", 1), 2)
    identity_path.write_text(json.dumps(identity, indent=2) + "\n")
    memory = load_iteration_memory(brand_dir)
    note_parts: list[str] = []
    if args.tagline:
        note_parts.append(f"Approved tagline: {args.tagline.strip()}")
    if args.elevator:
        note_parts.append(f"Approved elevator: {args.elevator.strip()}")
    if args.voice_description:
        note_parts.append(f"Voice direction: {args.voice_description.strip()}")
    if args.add_value_prop:
        note_parts.extend([f"Value prop: {item.strip()}" for item in args.add_value_prop if str(item).strip()])
    if note_parts:
        for item in note_parts[-5:]:
            memory = add_iteration_note(memory, item, bucket="messaging_notes")
        save_iteration_memory(brand_dir, memory)
    print(f"Messaging updated in {identity_path}")
    if args.format == "json":
        print(json.dumps(messaging, indent=2))
    else:
        if messaging.get("tagline"):
            print(f"Tagline: {messaging['tagline']}")
        if messaging.get("elevator"):
            print(f"Elevator: {messaging['elevator'][:120]}...")
        if messaging.get("value_propositions"):
            print(f"Value props: {len(messaging['value_propositions'])}")
        if copy_bank.get("headlines"):
            print(f"Headlines: {len(copy_bank['headlines'])}")
        if copy_bank.get("slogans"):
            print(f"Slogans: {len(copy_bank['slogans'])}")


def cmd_ideate_messaging(args):
    """Assemble brand context for messaging ideation. The calling agent generates the angles."""
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "Brand").strip()
    summary = ((identity.get("brand") or {}).get("summary") or profile.get("description") or "").strip()
    tone_words = (identity.get("identity_core") or {}).get("tone_words") or profile.get("keywords") or []
    identity_core = identity.get("identity_core") or {}
    messaging = identity.get("messaging") or {}
    memory = load_iteration_memory(brand_dir)
    copy_notes = memory.get("copy_notes") or []
    brand_notes = memory.get("brand_notes") or []
    messaging_notes = memory.get("messaging_notes") or []

    # Assemble full brand context for the calling agent to reason over
    context: dict = {
        "brand_name": brand_name,
        "summary": summary,
        "tone_words": tone_words[:10],
    }

    # Identity core signals
    if identity_core.get("approved_primitives"):
        context["visual_primitives"] = identity_core["approved_primitives"][:4]
    if identity_core.get("brand_truth_rules"):
        context["brand_truth_rules"] = identity_core["brand_truth_rules"][:3]
    if identity_core.get("forbidden_elements"):
        context["forbidden_elements"] = identity_core["forbidden_elements"][:3]

    # Current messaging state (what exists already)
    current: dict = {}
    if messaging.get("tagline"):
        current["tagline"] = messaging["tagline"]
    if messaging.get("elevator"):
        current["elevator"] = messaging["elevator"]
    if messaging.get("voice"):
        current["voice"] = messaging["voice"]
    if messaging.get("value_propositions"):
        current["value_propositions"] = messaging["value_propositions"]
    copy_bank = messaging.get("approved_copy_bank") or {}
    if copy_bank.get("headlines"):
        current["approved_headlines"] = copy_bank["headlines"]
    if copy_bank.get("slogans"):
        current["approved_slogans"] = copy_bank["slogans"]

    # Iteration history — what the team has said about messaging so far
    iteration: dict = {}
    if messaging_notes:
        iteration["messaging_notes"] = messaging_notes[-8:]
    if copy_notes:
        iteration["copy_notes"] = copy_notes[-5:]
    if brand_notes:
        iteration["brand_notes"] = brand_notes[-5:]
    # Include positioning/copy insights promoted from previous sessions
    if messaging.get("positioning_insights"):
        iteration["positioning_insights"] = messaging["positioning_insights"][-5:]
    if messaging.get("copy_insights"):
        iteration["copy_insights"] = messaging["copy_insights"][-5:]

    payload: dict = {
        "brand_context": context,
        "current_messaging": current if current else None,
        "iteration_history": iteration if iteration else None,
        "instructions": (
            "Generate 3-5 positioning angles for this brand. Each angle should have: "
            "a short label, a tagline (≤10 words), an elevator pitch (1-2 sentences), "
            "and a voice direction (1 sentence). Make each angle genuinely different — "
            "vary the framing, audience, and emotional register. Be specific to this product. "
            "Avoid: revolutionize, transform, unlock, empower, seamless, elevate, or any generic startup language."
        ),
        "next_steps": [
            "Pick an angle and run: update-messaging --tagline '<tagline>' --elevator '<elevator>'",
            "Or record a note: update-iteration-memory --kind messaging --note '<insight>'",
            "After iterating, promote to brand identity: promote-messaging",
        ],
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return

    # Human-readable summary
    print(f"Messaging ideation context for {brand_name}\n")
    print(f"Summary: {summary}")
    if tone_words:
        print(f"Tone: {', '.join(tone_words[:8])}")
    if current:
        print(f"\nCurrent messaging:")
        if current.get("tagline"):
            print(f"  Tagline: {current['tagline']}")
        if current.get("elevator"):
            print(f"  Elevator: {current['elevator'][:120]}...")
        if current.get("voice", {}).get("description"):
            print(f"  Voice: {current['voice']['description'][:100]}...")
        if current.get("value_propositions"):
            print(f"  Value props: {len(current['value_propositions'])}")
        if current.get("approved_headlines"):
            print(f"  Headlines: {len(current['approved_headlines'])}")
    if iteration:
        print(f"\nIteration history:")
        for key in ("messaging_notes", "copy_notes", "brand_notes", "positioning_insights", "copy_insights"):
            items = iteration.get(key) or []
            if items:
                print(f"  {key} ({len(items)}):")
                for note in items[-3:]:
                    print(f"    - {note}")
    print(f"\nThe agent should now generate 3-5 positioning angles from this context.")


def cmd_promote_messaging(args):
    """Promote session messaging (copy_notes + identity messaging) to the saved brand."""
    brand_gen_dir = get_brand_gen_dir()
    if not brand_gen_dir:
        raise SystemExit("No .brand-gen directory found.")
    brand_dir = get_brand_dir()
    config = load_brand_gen_config(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    active_brand = resolve_active_brand_key(brand_gen_dir=brand_gen_dir, repo_root=REPO_ROOT)
    if not active_brand:
        raise SystemExit("No active brand. Run: use <brand>")
    saved_identity_path = brand_gen_dir / "brands" / active_brand / "brand-identity.json"
    if not saved_identity_path.exists():
        raise SystemExit(f"Saved brand identity not found: {saved_identity_path}")

    # Load session identity and saved identity
    _, _, _, session_identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    saved_identity = load_json_file(saved_identity_path)

    # Merge messaging from session into saved brand
    session_messaging = session_identity.get("messaging") or {}
    saved_messaging = saved_identity.get("messaging") or {}

    if not session_messaging and not args.include_copy_notes:
        print("No messaging to promote. Run update-messaging first or use --include-copy-notes.")
        return

    # Promote structured messaging fields
    for field in ("tagline", "elevator"):
        if session_messaging.get(field):
            saved_messaging[field] = session_messaging[field]
    if session_messaging.get("voice"):
        saved_messaging["voice"] = session_messaging["voice"]
    if session_messaging.get("value_propositions"):
        existing = saved_messaging.get("value_propositions") or []
        for prop in session_messaging["value_propositions"]:
            if prop not in existing:
                existing.append(prop)
        saved_messaging["value_propositions"] = existing

    # Promote copy bank entries
    session_bank = session_messaging.get("approved_copy_bank") or {}
    saved_bank = saved_messaging.get("approved_copy_bank") or {}
    for bucket in ("headlines", "slogans", "subheadlines"):
        session_items = session_bank.get(bucket) or []
        saved_items = saved_bank.get(bucket) or []
        for item in session_items:
            if item not in saved_items:
                saved_items.append(item)
        if saved_items:
            saved_bank[bucket] = saved_items
    if session_bank.get("cta_pairs"):
        saved_bank["cta_pairs"] = session_bank["cta_pairs"]
    saved_messaging["approved_copy_bank"] = saved_bank

    # Optionally promote iteration notes as messaging insights (kept separate by type)
    if args.include_copy_notes:
        memory = load_iteration_memory(brand_dir)
        messaging_notes = list(memory.get("messaging_notes") or [])
        copy_notes = list(memory.get("copy_notes") or [])
        if messaging_notes:
            existing = saved_messaging.get("positioning_insights") or []
            for note in messaging_notes:
                if note not in existing:
                    existing.append(note)
            saved_messaging["positioning_insights"] = existing[-15:]
        if copy_notes:
            existing = saved_messaging.get("copy_insights") or []
            for note in copy_notes:
                if note not in existing:
                    existing.append(note)
            saved_messaging["copy_insights"] = existing[-15:]

    saved_identity["messaging"] = saved_messaging
    saved_identity["schema_version"] = max(saved_identity.get("schema_version", 1), 2)
    saved_identity_path.write_text(json.dumps(saved_identity, indent=2) + "\n")
    print(f"Messaging promoted to {saved_identity_path}")
    if saved_messaging.get("tagline"):
        print(f"  Tagline: {saved_messaging['tagline']}")
    if saved_messaging.get("elevator"):
        print(f"  Elevator: {saved_messaging['elevator'][:80]}...")
    if saved_messaging.get("value_propositions"):
        print(f"  Value props: {len(saved_messaging['value_propositions'])}")
    bank = saved_messaging.get("approved_copy_bank") or {}
    for bucket in ("headlines", "slogans", "subheadlines"):
        items = bank.get(bucket) or []
        if items:
            print(f"  {bucket.title()}: {len(items)}")

def cmd_plan_set(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, identity_path, profile, identity = load_brand_memory(brand_dir, args.profile, args.identity)
    template_key = (args.template or "product-core").strip().lower().replace("-", "_")
    template = MATERIAL_SET_TEMPLATES.get(template_key)
    if not template:
        raise SystemExit(f"Unknown set template '{args.template}'. Available: {', '.join(sorted(k.replace('_', '-') for k in MATERIAL_SET_TEMPLATES))}")
    brand_name = ((identity.get("brand") or {}).get("name") or profile.get("brand_name") or "brand").strip()
    set_slug = slugify(args.set_name or f"{brand_name}-{template_key}")
    goal = args.goal or template.get("description") or f"Build a {template_key.replace('_', ' ')} material set for {brand_name}."
    set_surface = args.surface or "multi-surface brand set"
    plans_dir = brand_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    materials: list[dict] = []
    for item in template.get("materials") or []:
        material_type = item["material_type"]
        policy = normalize_material_brand_policy(material_type, identity=identity)
        plan, missing_required = create_material_plan(
            brand_dir=brand_dir,
            identity_path=identity_path,
            identity=identity,
            material_type=material_type,
            mode=args.mode,
            mechanic=item.get("mechanic") or "",
            preserve=[],
            push=[],
            ban=[],
            picks={},
            purpose=item.get("purpose") or policy.get("purpose") or "",
            target_surface=item.get("target_surface") or args.surface or policy.get("target_surface") or "",
            product_truth_expression=item.get("product_truth_expression") or policy.get("product_truth_expression") or "",
            abstraction_level=item.get("abstraction_level") or policy.get("abstraction_level") or "",
            set_membership={
                "set_name": set_slug,
                "set_role": item.get("role") or policy.get("role") or "",
                "template": template_key,
            },
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
        plan_path = plans_dir / f"{set_slug}-{slugify(material_type)}.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        materials.append(
            {
                "material_type": plan.get("material_type") or material_type,
                "material_key": role_pack_material_key(plan.get("material_type") or material_type),
                "role": item.get("role") or policy.get("role") or "",
                "target_surface": plan.get("target_surface") or "",
                "product_truth_expression": plan.get("product_truth_expression") or "",
                "abstraction_level": plan.get("abstraction_level") or "",
                "preferred_engine": preferred_material_engine(material_type),
                "plan_path": str(plan_path),
                "missing_required_roles": missing_required,
                "brand_anchor_rule": (plan.get("brand_anchor_policy") or {}).get("rule") or "",
            }
        )
    payload = {
        "version": 1,
        "set_name": set_slug,
        "brand_name": brand_name,
        "brand_dir": str(brand_dir),
        "identity_path": str(identity_path),
        "template": template_key,
        "goal": goal,
        "surface": set_surface,
        "set_brand_rule": "Every material must either show the stored logo/wordmark or satisfy its explicit clearly-branded anchor rule before it belongs in the set.",
        "inspiration_translation": {
            "rule": "Use agency inspiration only as translated mechanics for composition, motif logic, application attitude, or motion pacing. Brand truth remains the identity source."
        },
        "materials": materials,
    }
    sets_dir = brand_dir / "sets"
    sets_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output).expanduser().resolve() if args.output else sets_dir / f"{set_slug}.json"
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    report = validate_set_manifest_dict(payload)
    if args.format == "json":
        print(json.dumps({"set": payload, "validation": report}, indent=2))
        return
    print(f"Material set written to: {output_path}\n")
    print(f"Brand: {brand_name}")
    print(f"Template: {template_key}")
    print(f"Goal: {goal}")
    print(f"Surface: {set_surface}")
    print(f"Validation: {'ok' if report['ok'] else 'needs work'} ({report['score']}/{report['max_score']})")
    print("\nMaterials:")
    for item in materials:
        print(f"- {item['material_type']}: {item['role']} [{item['preferred_engine']}]")
        print(f"  surface: {item['target_surface']}")
        print(f"  product truth: {item['product_truth_expression']}")
        print(f"  brand rule: {item['brand_anchor_rule']}")
        print(f"  plan: {item['plan_path']}")
    if report["warnings"]:
        print("\nWarnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")


def cmd_validate_brand_fit(args):
    if not args.plan and not args.set:
        raise SystemExit("Specify --plan or --set.")
    if args.plan:
        _, plan = load_plan_payload(Path(args.plan).expanduser().resolve())
        report = validate_material_plan_dict(plan)
    else:
        payload = load_json_file(Path(args.set).expanduser().resolve())
        report = validate_set_manifest_dict(payload)
    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Status: {'ok' if report['ok'] else 'needs work'}")
        print(f"Score: {report['score']}/{report['max_score']}")
        if report["errors"]:
            print("\nErrors:")
            for item in report["errors"]:
                print(f"- {item}")
        if report["warnings"]:
            print("\nWarnings:")
            for item in report["warnings"]:
                print(f"- {item}")
    if args.strict and (report["errors"] or report["warnings"]):
        sys.exit(1)
