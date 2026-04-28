from __future__ import annotations

from ..pipeline_request import PipelineRequest
from ..runtime import *
from ..material_planning import *
from ..generation_flow import *
from ..run_ledger import append_run_event
from ..session_summary import *
from ..media_board import *
from ..html_share_cards import execute_html_share_card_scratchpad
from ..launch_producer import create_video as _launch_create_video


def cmd_create_video(args):
    """Create a full launch video end-to-end from a brief JSON.
    The brief describes shots (source_version + motion prompt per shot) plus a
    timeline (video_tag or image segments with durations). Borrows derive-video's
    scratchpad infrastructure for each shot, then ffmpeg-stitches into one mp4.
    """
    brief_path = Path(getattr(args, "brief", "") or "").expanduser().resolve()
    if not brief_path.exists():
        raise SystemExit(f"brief not found: {brief_path}")
    result = _launch_create_video(brief_path, verbose=True)
    if getattr(args, "format", "text") == "json":
        print(json.dumps(result, indent=2))
        return
    print(f"\nLaunch video ready: {result['output_path']}")
    print(f"  version_id: {result['version_id']}")
    print(f"  duration:   ~{result['timeline_length']:.1f}s")
    print(f"  shots:      {', '.join(result['shots'])}")

def _build_derived_video_prompt(source_version: str, source_entry: dict, sidecar: dict, material_type: str) -> str:
    seed = (
        sidecar.get("execution_prompt")
        or sidecar.get("effective_prompt")
        or source_entry.get("raw_prompt")
        or ""
    ).strip()
    motion_goal = {
        "landing-hero": "Animate the approved still into a deployable landing-page hero background/sidecar loop with external hero copy.",
        "short-video": "Create a short branded motion piece from the approved still.",
        "feature-animation": "Animate the approved still into a polished feature reveal.",
        "motion-loop": "Animate the approved still into a seamless branded loop.",
    }.get(material_type, "Animate the approved still into a branded motion derivative.")
    preserve = (
        "Preserve brand palette, composition, visible logos or marks, and product-truth structure. "
        "Use subtle production-friendly motion and avoid morphing, hallucinated UI, rewritten text, or page chrome."
    )
    return f"{motion_goal} Source still context: {seed} {preserve}".strip() if seed else f"{motion_goal} {preserve}".strip()


def _load_derivative_sidecar(brand_dir: Path, source_version: str) -> dict:
    return load_json_file(brand_dir / f"{source_version}.prompts.json")


def _build_derived_mockup_prompt(source_version: str, source_entry: dict, sidecar: dict, material_type: str) -> str:
    seed = (
        sidecar.get("execution_prompt")
        or sidecar.get("effective_prompt")
        or source_entry.get("raw_prompt")
        or ""
    ).strip()
    scene_goal = {
        "device-mockup": "Present the approved branded still inside a believable premium device mockup scene.",
        "lifestyle-mockup": "Stage the approved branded still inside a believable premium lifestyle context.",
        "website-hero-illustration": "Reinterpret the approved branded still as an editorial illustration that anchors a product landing page hero slot.",
    }.get(material_type, "Present the approved branded still in a believable contextual mockup scene.")
    preserve = (
        "Treat the source still as visual truth for palette, mark usage, hero hierarchy, and product proof. "
        "Generate a context-rich presentation rather than a flat export, but do not invent unrelated brands, sterile floating cards, or exact-compositing claims."
    )
    return f"{scene_goal} Source still context: {seed} {preserve}".strip() if seed else f"{scene_goal} {preserve}".strip()


def cmd_generate(args):
    if not getattr(args, "scratchpad", None):
        print("ERROR: generate now requires --scratchpad. Build one first with build-generation-scratchpad.", file=sys.stderr)
        sys.exit(1)
    scratchpad_path = Path(args.scratchpad).expanduser().resolve()
    payload = load_json_file(scratchpad_path)
    payload["brand_dir"] = str(validate_brand_workspace_dir(payload.get("brand_dir") or "", label="scratchpad brand_dir"))
    payload["_scratchpad_path"] = str(scratchpad_path)

    max_iterations = getattr(args, "max_iterations", 1) or 1
    max_iterations = min(max(max_iterations, 1), 3)
    skip_vlm = bool(getattr(args, "skip_vlm", False))
    use_internal_vlm_critique = bool(getattr(args, "internal_vlm_critique", False)) and not skip_vlm
    agent_critique_path = getattr(args, "vlm_critique", None)

    if getattr(args, "internal_vlm_critique", False) and skip_vlm:
        print("Warning: --skip-vlm overrides --internal-vlm-critique; internal VLM critique will stay disabled.", file=sys.stderr)
    if max_iterations > 1 and not agent_critique_path and not use_internal_vlm_critique:
        print("Note: max_iterations > 1 but no visual critique source is enabled; generation will run single-shot unless you pass --vlm-critique or --internal-vlm-critique.", file=sys.stderr)

    _is_html = str(payload.get("render_backend") or "").strip().lower() == "html"
    if _is_html:
        vid = execute_html_share_card_scratchpad(payload)
        print(f"HTML share card generated: {vid}")
        return

    all_vids: list[str] = []
    current_payload = payload

    for iteration in range(max_iterations):
        iteration_label = f" (iteration {iteration + 1}/{max_iterations})" if max_iterations > 1 else ""
        print(f"\n{'=' * 60}\nGenerating{iteration_label}...\n{'=' * 60}")

        vid = execute_generation_scratchpad(current_payload)
        all_vids.append(vid)

        if not agent_critique_path and not use_internal_vlm_critique:
            break

        # --- Critique: prefer agent-provided, fall back to internal VLM ---
        brand_dir = validate_brand_workspace_dir(current_payload["brand_dir"], label="scratchpad brand_dir")
        manifest = load_manifest(brand_dir)
        entry = manifest["versions"].get(vid, {})
        image_files = [brand_dir / f for f in entry.get("files", []) if Path(f).suffix.lower() in SUPPORTED_IMAGE_EXTS]
        if not image_files or not image_files[0].exists():
            print("No image file to critique; stopping iteration loop.")
            break

        vlm_result: dict | None = None

        # 1) Agent-provided critique (no nested LLM call)
        if agent_critique_path:
            try:
                cpath = Path(agent_critique_path).expanduser().resolve()
                vlm_result = json.loads(cpath.read_text())
                vlm_result.setdefault("approved", not bool(vlm_result.get("p1")))
                vlm_result.setdefault("p1", [])
                vlm_result.setdefault("p2", [])
                vlm_result.setdefault("p3", [])
                vlm_result.setdefault("clean", [])
                vlm_result["vlm_available"] = True
                vlm_result["vlm_provider"] = "agent"
                print(f"\nUsing agent-provided critique for {vid}.")
            except Exception as exc:
                print(f"Warning: failed to load agent critique: {exc}", file=sys.stderr)
                vlm_result = None
            # Only use agent critique for the first iteration
            agent_critique_path = None

        # 2) Optional legacy internal VLM call (opt-in only; agents should use critique-rubric + submit-critique instead)
        if vlm_result is None and use_internal_vlm_critique:
            brief = current_payload.get("execution_prompt") or current_payload.get("effective_prompt") or ""
            board = load_blackboard(brand_dir)
            brand_dna = board.get("brand_dna") or {}
            print(f"\nRunning internal VLM critique on {vid}... (legacy opt-in path; prefer critique-rubric + submit-critique instead)")
            vlm_result = run_vlm_critique(image_files[0], brief, brand_dna)

        if vlm_result is None:
            break

        # Save critique alongside the auto-review
        vlm_path = brand_dir / "reviews" / f"{vid}-vlm-critique.json"
        vlm_path.parent.mkdir(parents=True, exist_ok=True)
        vlm_path.write_text(json.dumps(vlm_result, indent=2) + "\n")
        manifest["versions"][vid]["vlm_critique_path"] = str(vlm_path)
        manifest["versions"][vid]["vlm_critique"] = {
            "approved": vlm_result.get("approved", False),
            "p1_count": len(vlm_result.get("p1") or []),
            "p2_count": len(vlm_result.get("p2") or []),
            "palette_match": vlm_result.get("palette_match", 0),
            "logo_visible": vlm_result.get("logo_visible", False),
            "vlm_available": vlm_result.get("vlm_available", False),
            "provider": vlm_result.get("vlm_provider", "unknown"),
        }
        manifest["versions"][vid]["visual_review_status"] = "approved" if vlm_result.get("approved", False) else "needs_refinement"
        manifest["versions"][vid]["visual_review_provider"] = vlm_result.get("vlm_provider", "unknown")
        save_manifest(manifest, brand_dir)
        append_run_event(
            brand_dir,
            entry.get("workflow_id") or current_payload.get("workflow_id") or "",
            stage="review",
            event_type="vlm_critique_saved",
            attempt_id=vid,
            material_type=entry.get("material_type") or current_payload.get("material_type") or "",
            mode=entry.get("mode") or current_payload.get("workflow_mode") or "",
            model=entry.get("model") or ((current_payload.get("execution") or {}).get("model") or ""),
            provider=vlm_result.get("vlm_provider") or "agent",
            output_version=vid,
            status="approved" if vlm_result.get("approved") else "needs_refinement",
            data={"vlm_critique_path": str(vlm_path), "p1": list(vlm_result.get("p1") or []), "p2_count": len(vlm_result.get("p2") or [])},
        )

        # Update blackboard
        profile_path = current_payload.get("profile_path")
        identity_path = current_payload.get("identity_path")
        _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
        bb = load_blackboard(brand_dir, profile, identity)
        append_blackboard_decision(
            bb,
            agent="critic_agent",
            decision=f"Critique of {vid}: {'approved' if vlm_result.get('approved') else 'needs refinement'} "
                     f"(P1: {len(vlm_result.get('p1') or [])}, palette: {vlm_result.get('palette_match', 'n/a')}, "
                     f"provider: {vlm_result.get('vlm_provider', 'unknown')})",
            confidence=0.9 if vlm_result.get("vlm_provider") == "agent" else (0.85 if vlm_result.get("vlm_available") else 0.3),
            severity="P1" if vlm_result.get("p1") else ("P2" if vlm_result.get("p2") else None),
            data={"vlm_critique_path": str(vlm_path), "approved": vlm_result.get("approved", False)},
        )
        save_blackboard(brand_dir, bb)

        if not vlm_result.get("vlm_available"):
            print("Critique not available; stopping iteration loop.")
            break

        if vlm_result.get("approved"):
            print(f"✅ Critique approved {vid}. No further iterations needed.")
            break

        # --- Refine prompt for next iteration ---
        print(f"🔄 Critique flagged issues on {vid}. Refining prompt for iteration {iteration + 2}...")
        if vlm_result.get("p1"):
            print(f"   P1 issues: {'; '.join(str(i) for i in vlm_result['p1'][:3])}")
        if vlm_result.get("refinement_suggestion"):
            print(f"   Suggestion: {vlm_result['refinement_suggestion']}")

        if iteration >= max_iterations - 1:
            break

        refined_prompt = refine_prompt_from_vlm_critique(
            current_payload.get("execution_prompt") or current_payload.get("effective_prompt") or "",
            vlm_result,
        )
        current_payload = dict(current_payload)
        current_payload["execution_prompt"] = refined_prompt
        if not current_payload.get("effective_prompt"):
            current_payload["effective_prompt"] = refined_prompt
        current_payload["_iteration"] = iteration + 1
        current_payload["_previous_vid"] = vid
        current_payload["_vlm_critique"] = vlm_result


def cmd_generate_once(args):
    if not getattr(args, "scratchpad", None):
        raise SystemExit("generate-once requires --scratchpad.")
    scratchpad_path = Path(args.scratchpad).expanduser().resolve()
    payload = load_json_file(scratchpad_path)
    payload["brand_dir"] = str(validate_brand_workspace_dir(payload.get("brand_dir") or "", label="scratchpad brand_dir"))
    payload["_scratchpad_path"] = str(scratchpad_path)
    if str(payload.get("render_backend") or "").strip().lower() == "html":
        version_id = execute_html_share_card_scratchpad(payload)
    else:
        version_id = execute_generation_scratchpad(payload)
    brand_dir = validate_brand_workspace_dir(payload["brand_dir"], label="scratchpad brand_dir")
    manifest = load_manifest(brand_dir)
    entry = (manifest.get("versions") or {}).get(version_id) or {}
    image_paths = [
        str((brand_dir / name).resolve())
        for name in (entry.get("files") or [])
        if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS and (brand_dir / name).exists()
    ]
    result = {
        "version_id": version_id,
        "image_paths": image_paths,
        "scratchpad_path": str(scratchpad_path),
        "workflow_id": entry.get("workflow_id") or payload.get("workflow_id") or "",
    }
    _open_flag = getattr(args, "open", False)
    if getattr(args, "format", "json") == "json":
        print(json.dumps(result, indent=2))
        if _open_flag and image_paths and sys.platform == "darwin":
            subprocess.run(["open", image_paths[0]], check=False)
        return
    print(f"Generated {version_id}")
    for path in image_paths:
        print(f"  {path}")
    if image_paths and sys.platform == "darwin":
        subprocess.run(["open", image_paths[0]], check=False)


def cmd_derive_video(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(brand_dir)
    source_version = str(getattr(args, "source_version", "") or "").strip()
    if not source_version:
        raise SystemExit("derive-video requires --source-version.")
    source_entry = (manifest.get("versions") or {}).get(source_version) or {}
    if not source_entry:
        raise SystemExit(f"Source version '{source_version}' not found.")

    image_paths = [
        brand_dir / name
        for name in (source_entry.get("files") or [])
        if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS and (brand_dir / name).exists()
    ]
    if not image_paths:
        raise SystemExit(f"Source version '{source_version}' has no available image file to animate.")

    material_type = normalize_material_type(getattr(args, "material_type", None) or "short-video")
    config = MATERIAL_CONFIG.get(material_type) or {}
    if config.get("generation_mode") != "video":
        raise SystemExit(f"Material type '{material_type}' is not configured for video generation.")

    workflow_id = resolve_workflow_id({})
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    sidecar = _load_derivative_sidecar(brand_dir, source_version)
    prompt = str(getattr(args, "prompt", None) or _build_derived_video_prompt(source_version, source_entry, sidecar, material_type)).strip()
    model = getattr(args, "model", None) or config.get("default_model") or "kling-v2.6"
    aspect_ratio = getattr(args, "aspect_ratio", None) or source_entry.get("aspect_ratio") or config.get("default_aspect_ratio") or "16:9"
    payload = {
        "schema_type": "generation_scratchpad",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "brand_dir": str(brand_dir),
        "workflow_id": workflow_id,
        "source_version": source_version,
        "branch_id": workflow_id,
        "parent_branch_id": source_entry.get("branch_id") or source_entry.get("workflow_id") or "",
        "branch_status": "active",
        "material_type": material_type,
        "tag": getattr(args, "tag", None) or material_type,
        "workflow_mode": source_entry.get("mode") or "hybrid",
        "generation_mode": "video",
        "profile_path": str(profile_path),
        "identity_path": str(identity_path),
        "raw_prompt": prompt,
        "effective_prompt": prompt,
        "execution_prompt": prompt,
        "prompt_context": {
            "brand_prelude": "",
            "material_prompt_snippet": "",
            "reference_role_pack_snippet": "",
            "inspiration_doctrine": "",
            "reference_role_pack": [],
            "token_block": "",
            "token_block_fragments": [],
        },
        "prompt_review": {},
        "checks": {"blocking": [], "warnings": []},
        "reference_context": {
            "passed_reference_paths": [str(image_paths[0])],
            "all_context_refs": [str(image_paths[0])],
        },
        "selected_reference_ids": list(source_entry.get("selected_reference_ids") or []),
        "selected_inspiration_ids": list(source_entry.get("selected_inspiration_ids") or []),
        "derivative_mode": "generated_mockup_scene",
        "execution": {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "duration": getattr(args, "duration", None),
            "motion_reference": getattr(args, "motion_reference", None),
            "negative_prompt": getattr(args, "negative_prompt", None),
            "make_gif": bool(getattr(args, "make_gif", False)),
        },
    }
    output_path = save_generation_scratchpad(brand_dir, payload, label=f"{source_version}-{material_type}")
    persist_generation_scratchpad_to_blackboard(brand_dir, profile, identity, payload, output_path=output_path, workflow_id=workflow_id)
    append_run_event(
        brand_dir,
        workflow_id,
        stage="scratchpad",
        event_type="derived_video_scratchpad_built",
        material_type=material_type,
        mode=payload.get("workflow_mode") or "",
        model=model,
        source_version=source_version,
        status="ok",
        data={"output_path": str(output_path)},
    )
    payload["_scratchpad_path"] = str(output_path)
    version_id = execute_generation_scratchpad(payload, workflow_id=workflow_id)
    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "source_version": source_version,
                    "material_type": material_type,
                    "mockup_mode": "generated_scene_not_precise_composite",
                    "workflow_id": workflow_id,
                    "scratchpad": str(output_path),
                    "version_id": version_id,
                },
                indent=2,
            )
        )
        return
    print(f"Derived video: {version_id}")
    print(f"Scratchpad: {output_path}")


def cmd_derive_mockup(args):
    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(brand_dir)
    source_version = str(getattr(args, "source_version", "") or "").strip()
    if not source_version:
        raise SystemExit("derive-mockup requires --source-version.")
    source_entry = (manifest.get("versions") or {}).get(source_version) or {}
    if not source_entry:
        raise SystemExit(f"Source version '{source_version}' not found.")

    image_paths = [
        brand_dir / name
        for name in (source_entry.get("files") or [])
        if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS and (brand_dir / name).exists()
    ]
    if not image_paths:
        raise SystemExit(f"Source version '{source_version}' has no available image file to mock up.")

    material_type = normalize_material_type(getattr(args, "material_type", None) or "device-mockup")
    config = MATERIAL_CONFIG.get(material_type) or {}
    if config.get("generation_mode") != "image":
        raise SystemExit(f"Material type '{material_type}' is not configured for image generation.")

    workflow_id = resolve_workflow_id({})
    profile_path, identity_path, profile, identity = load_brand_memory(brand_dir, getattr(args, "profile", None), getattr(args, "identity", None))
    sidecar = _load_derivative_sidecar(brand_dir, source_version)
    prompt = str(getattr(args, "prompt", None) or _build_derived_mockup_prompt(source_version, source_entry, sidecar, material_type)).strip()
    model = getattr(args, "model", None) or config.get("default_model") or "flux-2-pro"
    aspect_ratio = getattr(args, "aspect_ratio", None) or config.get("default_aspect_ratio") or source_entry.get("aspect_ratio") or "4:5"
    payload = {
        "schema_type": "generation_scratchpad",
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "brand_dir": str(brand_dir),
        "workflow_id": workflow_id,
        "source_version": source_version,
        "branch_id": workflow_id,
        "parent_branch_id": source_entry.get("branch_id") or source_entry.get("workflow_id") or "",
        "branch_status": "active",
        "material_type": material_type,
        "tag": getattr(args, "tag", None) or material_type,
        "workflow_mode": source_entry.get("mode") or "reference",
        "generation_mode": "image",
        "profile_path": str(profile_path),
        "identity_path": str(identity_path),
        "raw_prompt": prompt,
        "effective_prompt": prompt,
        "execution_prompt": prompt,
        "prompt_context": {
            "brand_prelude": "",
            "material_prompt_snippet": "",
            "reference_role_pack_snippet": "",
            "inspiration_doctrine": "",
            "reference_role_pack": [],
            "token_block": "",
            "token_block_fragments": [],
        },
        "prompt_review": {},
        "checks": {"blocking": [], "warnings": []},
        "reference_context": {
            "passed_reference_paths": [str(image_paths[0])],
            "all_context_refs": [str(image_paths[0])],
        },
        "selected_reference_ids": list(source_entry.get("selected_reference_ids") or []),
        "selected_inspiration_ids": list(source_entry.get("selected_inspiration_ids") or []),
        "derivative_mode": "generated_mockup_scene",
        "execution": {
            "model": model,
            "aspect_ratio": aspect_ratio,
            "negative_prompt": getattr(args, "negative_prompt", None),
        },
    }
    output_path = save_generation_scratchpad(brand_dir, payload, label=f"{source_version}-{material_type}")
    persist_generation_scratchpad_to_blackboard(brand_dir, profile, identity, payload, output_path=output_path, workflow_id=workflow_id)
    append_run_event(
        brand_dir,
        workflow_id,
        stage="scratchpad",
        event_type="derived_mockup_scratchpad_built",
        material_type=material_type,
        mode=payload.get("workflow_mode") or "",
        model=model,
        source_version=source_version,
        status="ok",
        data={"output_path": str(output_path)},
    )
    payload["_scratchpad_path"] = str(output_path)
    version_id = execute_generation_scratchpad(payload, workflow_id=workflow_id)
    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "source_version": source_version,
                    "material_type": material_type,
                    "mockup_mode": "generated_scene_not_precise_composite",
                    "workflow_id": workflow_id,
                    "scratchpad": str(output_path),
                    "version_id": version_id,
                },
                indent=2,
            )
        )
        return
    print(f"Derived mockup: {version_id}")
    print(f"Scratchpad: {output_path}")
    print("Mode: generated mockup scene (not pixel-precise compositing)")


def _build_pipeline_runner_from_request(request: PipelineRequest, *, workflow_id: str = ""):
    from ..pipeline_runner import PipelineRunner

    brand_dir = get_brand_dir()
    brand_dir.mkdir(parents=True, exist_ok=True)
    _, _, profile, identity = load_brand_memory(brand_dir, request.profile, request.identity)
    runner = PipelineRunner(
        brand_dir=brand_dir,
        profile=profile,
        identity=identity,
        **request.runner_kwargs(),
    )
    if workflow_id:
        runner.workflow_id = str(workflow_id)
    return runner, brand_dir, profile, identity


def _print_orchestration_payload(payload: dict, *, format: str = "json") -> None:
    if format == "json":
        print(json.dumps(payload, indent=2))
        return
    print(json.dumps(payload, indent=2))


def cmd_prepare_run(args):
    request = PipelineRequest.from_namespace(args)
    runner, _, _, _ = _build_pipeline_runner_from_request(request)
    payload = runner.prepare_run(request.to_namespace()).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_plan_run(args):
    request = PipelineRequest.from_namespace(args)
    runner, _, _, _ = _build_pipeline_runner_from_request(
        request,
        workflow_id=str(getattr(args, "workflow_id", "") or ""),
    )
    payload = runner.plan_run(request.to_namespace()).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_validate_run(args):
    request = PipelineRequest.from_namespace(args)
    workflow_id = str(getattr(args, "workflow_id", "") or "")
    if not workflow_id:
        draft_payload = load_json_file(Path(args.plan_draft).expanduser().resolve())
        workflow_id = str((draft_payload or {}).get("workflow_id") or "")
    runner, _, _, _ = _build_pipeline_runner_from_request(request, workflow_id=workflow_id)
    payload = runner.validate_run(getattr(args, "plan_draft")).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_execute_run(args):
    request = PipelineRequest.from_namespace(args)
    workflow_id = str(getattr(args, "workflow_id", "") or "")
    if not workflow_id:
        draft_payload = load_json_file(Path(args.plan_draft).expanduser().resolve())
        workflow_id = str((draft_payload or {}).get("workflow_id") or "")
    runner, _, _, _ = _build_pipeline_runner_from_request(request, workflow_id=workflow_id)
    payload = runner.execute_run(
        getattr(args, "plan_draft"),
        critique_path=getattr(args, "critique_path", None),
    ).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_review_run(args):
    request = PipelineRequest.from_namespace(args)
    runner, _, _, _ = _build_pipeline_runner_from_request(
        request,
        workflow_id=str(getattr(args, "workflow_id", "") or ""),
    )
    payload = runner.review_run(str(getattr(args, "version_id", "") or "")).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_evolve_run(args):
    request = PipelineRequest.from_namespace(args)
    runner, _, _, _ = _build_pipeline_runner_from_request(
        request,
        workflow_id=str(getattr(args, "workflow_id", "") or ""),
    )
    payload = runner.evolve_run(str(getattr(args, "version_id", "") or "")).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_orchestrate_material(args):
    request = PipelineRequest.from_namespace(args)
    runner, _, _, _ = _build_pipeline_runner_from_request(request)
    payload = runner.orchestrate_material(request.to_namespace()).to_dict()
    _print_orchestration_payload(payload, format=getattr(args, "format", "json"))


def cmd_pipeline(args):
    request = PipelineRequest.from_namespace(args)
    runner, brand_dir, profile, identity = _build_pipeline_runner_from_request(request)
    result = runner.run(request.to_namespace())
    payload = result.to_dict()
    # Add identity freshness and improvement questions to pipeline output
    manifest = load_manifest()
    freshness = check_identity_freshness(brand_dir, manifest, identity)
    questions = build_improvement_questions(brand_dir, profile, identity, manifest)
    if freshness["needs_rebuild"] or questions:
        payload["agent_guidance"] = {}
        if freshness["needs_rebuild"]:
            payload["agent_guidance"]["identity_rebuild_recommended"] = True
            payload["agent_guidance"]["rebuild_reasons"] = freshness["reasons"]
            if freshness.get("rebuild_note"):
                payload["agent_guidance"]["rebuild_note"] = freshness["rebuild_note"]
            if freshness.get("absorbable_learnings"):
                payload["agent_guidance"]["absorbable_learnings"] = freshness["absorbable_learnings"]
        if questions:
            # Prefer actionable questions over auto-resolved ones
            actionable = [q for q in questions if not q.get("auto_resolved")]
            payload["agent_guidance"]["improvement_questions"] = (actionable or questions)[:2]
    # Auto-open generated image when --open is set or in non-JSON (terminal) mode
    _should_open = (
        result.stopped_at == "complete"
        and result.result
        and result.result.image_paths
    )
    _open_flag = getattr(args, "open", False)

    if getattr(args, "format", "json") == "json":
        print(json.dumps(payload, indent=2))
        if _should_open and _open_flag and sys.platform == "darwin":
            subprocess.run(["open", result.result.image_paths[0]], check=False)
        if result.stopped_at not in {"complete", "critique"}:
            sys.exit(1)
        return

    print("Pipeline result\n")
    print(f"Workflow ID: {result.workflow_id}")
    print(f"Stopped at: {result.stopped_at or 'unknown'}")
    print(f"Reason: {result.stop_reason or 'n/a'}")
    if result.route:
        print(f"Route: {result.route.route_key} ({result.route.method}, score={result.route.score:.2f})")
    if result.plan_draft and result.plan_draft.output_path:
        print(f"Plan draft: {result.plan_draft.output_path}")
    if result.critique and result.critique.output_path:
        print(f"Critique: {result.critique.output_path}")
    if result.scratchpad and result.scratchpad.output_path:
        print(f"Scratchpad: {result.scratchpad.output_path}")
    if result.result:
        print(f"Generated: {result.result.version_id}")
        if result.result.image_paths:
            for img_path in result.result.image_paths:
                print(f"  {img_path}")
    if _should_open and sys.platform == "darwin":
        subprocess.run(["open", result.result.image_paths[0]], check=False)
    if result.stopped_at not in {"complete", "critique"}:
        sys.exit(1)

def cmd_generate_set(args):
    payload = load_json_file(Path(args.set).expanduser().resolve())
    report = validate_set_manifest_dict(payload)
    if not report["ok"]:
        raise SystemExit("Set validation failed. Run validate-set or validate-brand-fit first and fix the errors.")
    only = {item.strip() for item in (args.only or []) if item.strip()}
    skip = {item.strip() for item in (args.skip or []) if item.strip()}
    parallel = getattr(args, "parallel", False)
    max_workers = min(getattr(args, "workers", 3) or 3, 5)

    to_generate: list[dict] = []
    skipped: list[str] = []
    for item in payload.get("materials") or []:
        material_type = item.get("material_type") or ""
        if only and material_type not in only:
            continue
        if material_type in skip:
            skipped.append(f"{material_type}: skipped by user")
            continue
        engine = item.get("preferred_engine") or "generate"
        if engine != "generate":
            skipped.append(f"{material_type}: preferred engine is {engine}")
            continue
        to_generate.append(item)

    generated: list[str] = []
    failed: list[str] = []

    if parallel and len(to_generate) > 1:
        print(f"Generating {len(to_generate)} materials in parallel (max {max_workers} workers)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _generate_set_member,
                    item,
                    getattr(args, "model", None),
                    getattr(args, "aspect_ratio", None),
                ): item
                for item in to_generate
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result["ok"]:
                    generated.append(result["material_type"])
                    if result.get("stdout"):
                        print(result["stdout"])
                else:
                    failed.append(f"{result['material_type']}: {result['error']}")
                    print(f"FAILED: {result['material_type']}: {result['error']}", file=sys.stderr)
    else:
        # Sequential (original behavior)
        for item in to_generate:
            material_type = item.get("material_type") or ""
            plan_path = item.get("plan_path") or ""
            scratch_cmd = [sys.executable, str(Path(__file__).resolve()), "build-generation-scratchpad", "--plan", plan_path, "--format", "json"]
            if args.model:
                scratch_cmd += ["--model", args.model]
            if args.aspect_ratio:
                scratch_cmd += ["--aspect-ratio", args.aspect_ratio]
            scratch_result = subprocess.run(scratch_cmd, capture_output=True, text=True)
            if scratch_result.returncode != 0:
                if scratch_result.stdout:
                    print(scratch_result.stdout)
                if scratch_result.stderr:
                    print(scratch_result.stderr, file=sys.stderr)
                raise SystemExit(scratch_result.returncode)
            scratch_payload = json.loads(scratch_result.stdout)
            scratchpad_path = scratch_payload["output"]
            cmd = [sys.executable, str(Path(__file__).resolve()), "generate", "--scratchpad", scratchpad_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                print(result.stdout)
            if result.returncode != 0:
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                raise SystemExit(result.returncode)
            generated.append(material_type)

    print(f"\nGenerated from set: {', '.join(generated) or 'none'}")
    if failed:
        print("Failed:")
        for item in failed:
            print(f"- {item}")
    if skipped:
        print("Skipped:")
        for item in skipped:
            print(f"- {item}")
