"""Campaign Runner orchestrating the multi-agent control plane campaign flow."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

from brand_gen.harness.session import BrandSession
from brand_gen.harness.policy import RunPolicy, ApprovalTrigger
from brand_gen.harness.events import RunEvent
from brand_gen.pipeline_types import OrchestrateMaterialResponse

async def query_agent(lm: Any, agent_id: str, user_text: str, expected_json: bool = False) -> str | dict[str, Any]:
    """Helper to load system prompts and query agent personas safely inside a thread executor."""
    from brand_gen.harness.critique.panel import load_agent_prompt
    from brand_gen.scoring.program import _extract_json_dict, _extract_text

    try:
        system_prompt = load_agent_prompt(agent_id)
    except Exception as exc:
        if expected_json:
            return {"error": f"Failed to load agent prompt: {exc}"}
        return f"Failed to load agent prompt: {exc}"

    messages = [
        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
        {"role": "user", "content": [{"type": "text", "text": user_text}]},
    ]

    loop = asyncio.get_running_loop()
    try:
        raw = await loop.run_in_executor(None, lambda: lm(messages=messages))
        text = _extract_text(raw)
        if expected_json:
            return _extract_json_dict(text)
        return text
    except Exception as exc:
        if expected_json:
            return {"error": f"LM execution failed: {exc}"}
        return f"LM execution failed: {exc}"

async def run_campaign_harness(brand_dir: Path, plan_args: argparse.Namespace) -> OrchestrateMaterialResponse:
    """Async campaign execution harness bypassing the legacy pipeline.
    
    Coordinates Strategist, Art Director, Prompt Engineer, Generator, Critic Panel, and Synthesizer.
    """
    from brand_gen.runtime import load_brand_memory, load_manifest, SUPPORTED_IMAGE_EXTS
    from brand_gen.custom_scratchpad import load_custom_scratchpad_json, load_custom_scratchpad_markdown
    from brand_gen.material_planning import build_material_plan_from_args, save_plan_draft, persist_plan_draft_to_blackboard
    from brand_gen.pipeline_request import PipelineRequest
    from brand_gen.generation_flow import assemble_generation_scratchpad, save_generation_scratchpad, persist_generation_scratchpad_to_blackboard
    from brand_gen.html_share_cards import execute_html_share_card_scratchpad
    from brand_gen.generation_flow import execute_generation_scratchpad
    from brand_gen.scoring.config import configure_judge_lm

    brand_dir = Path(brand_dir).expanduser().resolve()
    workflow_id = getattr(plan_args, "workflow_id", None) or uuid.uuid4().hex[:12]
    campaign_id = getattr(plan_args, "campaign_id", None) or f"camp_{workflow_id}"
    material_type = getattr(plan_args, "material_type", "share_card")

    # 1. Initialize active BrandSession and RunPolicy with pre_paid_generation trigger enabled
    policy = RunPolicy(
        approval_triggers=[
            ApprovalTrigger(name="pre_paid_generation", mode="sync"),
        ]
    )
    session = BrandSession(brand_dir, run_policy=policy)
    session.create_run(campaign_id, workflow_id)

    source_version = getattr(plan_args, "source_version", None) or ""
    parent_branch_id = ""
    if source_version:
        try:
            manifest = load_manifest(brand_dir)
            source_entry = manifest.get("versions", {}).get(source_version) or {}
            parent_branch_id = source_entry.get("branch_id") or source_entry.get("workflow_id") or ""
        except Exception as exc:
            print(f"Warning: Failed to resolve lineage for {source_version}: {exc}")

    # Log campaign start
    event_start = RunEvent(
        stage="orchestration",
        event_type="campaign_started",
        material_type=material_type,
        mode=getattr(plan_args, "mode", "hybrid"),
        status="ok",
        notes="Started campaign runner harness flow",
        branch_id=workflow_id,
        parent_branch_id=parent_branch_id,
    )
    session.log_event(event_start)

    # PR-5: write a campaign-tier memory event so cross-session learning is
    # bounded by purpose, not by raw run logs. Failure here must not block
    # the campaign — memory is observational, not gating.
    try:
        from brand_gen.memory import append_event_to_ledger, trigger_summarization

        append_event_to_ledger(
            brand_dir,
            "campaign",
            "campaign_started",
            {
                "campaign_id": campaign_id,
                "workflow_id": workflow_id,
                "material_type": material_type,
                "mode": getattr(plan_args, "mode", "hybrid"),
                "details": {
                    "source_version": source_version,
                    "parent_branch_id": parent_branch_id,
                },
            },
        )
        if parent_branch_id:
            append_event_to_ledger(
                brand_dir,
                "campaign",
                "branch_created",
                {
                    "branch_id": workflow_id,
                    "parent_branch_id": parent_branch_id,
                },
            )
        trigger_summarization(brand_dir, "campaign")
    except Exception as exc:
        print(f"Warning: memory tier campaign write failed: {exc}")

    # 2. Retrieve memory contexts
    profile_path = getattr(plan_args, "profile", None)
    identity_path = getattr(plan_args, "identity", None)
    _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)

    identity_context = {
        "profile": profile,
        "identity": identity,
        "custom_scratchpad_json": load_custom_scratchpad_json(brand_dir),
        "custom_scratchpad_md": load_custom_scratchpad_markdown(brand_dir),
    }

    # 3. Configure judge LM
    lm = configure_judge_lm()

    # Step 1: Strategist writes the creative Thesis / Brief
    goal = getattr(plan_args, "goal", "") or ""
    request = getattr(plan_args, "request", "") or ""
    
    strategist_user_text = f"""
We are starting a campaign for '{material_type}'.

Goal: {goal}
Request: {request}

Brand Identity and Scratchpad Context:
{json.dumps(identity_context, indent=2)}

Please author a detailed Creative Thesis / Brief for this campaign.
Target the v2 rubric axes (such as story_fidelity, meaning_clarity, restraint, brand_specificity).
Establish the visual strategy and causal logic.
Format your response as a high-quality Markdown document.
"""

    creative_brief = await query_agent(lm, "strategist", strategist_user_text, expected_json=False)

    # Step 2: Art Director drafts 2-3 visual directions
    art_director_user_text = f"""
We are designing visual directions for a '{material_type}' campaign based on the following Creative Thesis:
{creative_brief}

Please draft 2-3 distinct visual directions or cinematic shot layouts.
You must return a JSON object with a single "directions" list.
Each direction must contain:
- "direction_id": unique identifier (e.g. "direction_1", "direction_2")
- "name": descriptive title
- "visual_description": detailed visual/cinematographic description including lighting, environment, shot angle
- "composition_rules": list of 2-3 specific rules or constraints for the composition

Return ONLY valid JSON.
"""

    art_director_response = await query_agent(lm, "art-director", art_director_user_text, expected_json=True)
    if "directions" not in art_director_response or not isinstance(art_director_response["directions"], list):
        directions = [
            {
                "direction_id": "direction_1",
                "name": "Default Editorial Layout",
                "visual_description": f"A refined, premium visual layout for {material_type} featuring Sage branding colors, ample negative space, clean geometric proportions, and soft natural directional light.",
                "composition_rules": ["Keep the design clean and uncluttered.", "Ensure clear structural visual balance."]
            }
        ]
    else:
        directions = art_director_response["directions"]

    # Check if capability has custom build_prompts overrides
    from brand_gen.materials import fetch_material_capability
    capability = fetch_material_capability(material_type)
    
    custom_prompts = {}
    if capability is not None:
        try:
            # Prepare context for build_prompts
            context = {
                "brand_dir": brand_dir,
                "goal": goal,
                "request": request,
                "creative_brief": creative_brief,
                "directions": directions,
                "plan_args": plan_args,
                "identity_context": identity_context,
            }
            custom_prompts = capability.build_prompts(context)
        except Exception as exc:
            print(f"Warning: Failed to call build_prompts on capability: {exc}")

    # Step 3: Prompt Engineer writes a high-fidelity physical prompt for each direction
    directions_with_prompts = []
    if custom_prompts and "directions" in custom_prompts:
        directions_with_prompts = custom_prompts["directions"]
    else:
        async def run_prompt_engineer(direction: dict) -> dict:
            if custom_prompts and direction.get("direction_id") in custom_prompts:
                physical_prompt = custom_prompts[direction.get("direction_id")]
            elif custom_prompts and "physical_prompt" in custom_prompts:
                physical_prompt = custom_prompts["physical_prompt"]
            else:
                prompt_eng_user_text = f"""
We need to translate the following visual direction into a high-fidelity image/generation prompt:
Direction Name: {direction.get("name")}
Visual Description: {direction.get("visual_description")}
Composition Rules: {direction.get("composition_rules")}

Please write a concise, high-density physical prompt (60-100 words).
- Avoid generic AI quality-boosters (4K, masterpiece, ultra-realistic).
- Focus on physical lighting details (source, angle, intensity, temperature).
- Specify exact material textures, surface finishes, and camera perspectives.
- Strictly adhere to forbidden patterns. Do not request specific text characters.

Return a JSON object with:
- "physical_prompt": "the detailed physical prompt string"

Return ONLY valid JSON.
"""
                resp = await query_agent(lm, "prompt-engineer", prompt_eng_user_text, expected_json=True)
                physical_prompt = resp.get("physical_prompt") or direction.get("visual_description")
            
            return {
                "direction_id": direction.get("direction_id"),
                "name": direction.get("name"),
                "visual_description": direction.get("visual_description"),
                "composition_rules": direction.get("composition_rules"),
                "physical_prompt": physical_prompt,
            }

        prompt_tasks = [run_prompt_engineer(d) for d in directions]
        directions_with_prompts = await asyncio.gather(*prompt_tasks)

    # Step 4: Generator selects the best model from allowed models
    allowed_models = list(policy.allowed_models)
    if capability is not None and capability.default_model:
        if capability.default_model not in allowed_models:
            allowed_models.insert(0, capability.default_model)
    generator_user_text = f"""
You are the generator agent. Your task is to select the best model from the allowed models list for the generation prompt below.
Allowed Models: {allowed_models}

Generation Prompt:
"{directions_with_prompts[0]['physical_prompt']}"

Select the single best model from the list.
Return a JSON object with:
- "chosen_model": "the selected model name"
- "rationale": "a short justification for the selection"

Return ONLY valid JSON.
"""

    generator_response = await query_agent(lm, "generator", generator_user_text, expected_json=True)
    chosen_model = generator_response.get("chosen_model")
    if chosen_model not in allowed_models:
        chosen_model = allowed_models[0] if allowed_models else "flux-2-pro"

    # Step 5: Execute Generation + Concurrent Critique Panel for each direction
    async def execute_generation_for_direction(dir_item: dict, idx: int) -> dict:
        dir_args = copy.deepcopy(plan_args)
        dir_args.prompt_seed = dir_item["physical_prompt"]
        if chosen_model and chosen_model != "html:chromium":
            dir_args.model = chosen_model

        # Build material plan
        _, plan_dict, missing = build_material_plan_from_args(dir_args, brand_dir)

        # Create plan draft dict
        draft_dict = {
            "schema_type": "plan_draft",
            "schema_version": 1,
            "workflow_id": workflow_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "state": {"status": "drafted", "owner": "brand_director", "next_owner": "critic_agent"},
            "plan": plan_dict,
            "derived": {
                "selected_role_names": [
                    str(item.get("role", "")).strip()
                    for item in ((plan_dict.get("role_pack") or {}).get("selected_roles") or [])
                    if str(item.get("role", "")).strip()
                ],
                "missing_required_roles": missing,
            },
            "next_step": "Run critique-plan on this draft before building a generation scratchpad.",
        }

        plan_draft_path = save_plan_draft(
            brand_dir,
            draft_dict,
            label=f"{plan_dict.get('material_type', 'material')}-{plan_dict.get('mode', 'mode')}-plan-draft-{dir_item['direction_id']}",
            workflow_id=workflow_id,
        )

        persist_plan_draft_to_blackboard(
            brand_dir,
            profile,
            identity,
            draft_dict,
            output_path=plan_draft_path,
            workflow_id=workflow_id,
        )

        # Assemble scratchpad
        scratchpad_args = PipelineRequest.build_scratchpad_namespace(
            str(plan_draft_path),
            plan_dict,
            critique_mode=getattr(plan_args, "critique_mode", "strict"),
            allow_blocking=getattr(plan_args, "allow_blocking", False),
            source_version=source_version,
            base_image=getattr(plan_args, "base_image", None),
            tag=getattr(plan_args, "tag", None),
            render_backend=getattr(plan_args, "render_backend", "native"),
            source_url=getattr(plan_args, "source_url", None),
            entity_type=getattr(plan_args, "entity_type", None),
            headline=getattr(plan_args, "headline", None),
            subhead=getattr(plan_args, "subhead", None),
            cta=getattr(plan_args, "cta", None),
            proof_title=getattr(plan_args, "proof_title", None),
            proof_excerpt=getattr(plan_args, "proof_excerpt", None),
            proof_row=getattr(plan_args, "proof_row", None),
            proof_meta=getattr(plan_args, "proof_meta", None),
            proof_crop_path=getattr(plan_args, "proof_crop_path", None),
            skip_proof=getattr(plan_args, "skip_proof", False),
            dark_mode=getattr(plan_args, "dark_mode", False),
            design_variance=getattr(plan_args, "design_variance", 5),
            layout_spec=getattr(plan_args, "layout_spec", None),
            branch_id=workflow_id,
            parent_branch_id=parent_branch_id,
        )

        scratchpad_payload = assemble_generation_scratchpad(
            scratchpad_args,
            brand_dir=brand_dir,
            plan_wrapper=draft_dict,
            plan=plan_dict,
        )
        scratchpad_payload["workflow_id"] = workflow_id
        
        scratchpad_path = save_generation_scratchpad(
            brand_dir,
            scratchpad_payload,
            label=f"{scratchpad_payload.get('material_type', 'material')}-{scratchpad_payload.get('workflow_mode', 'mode')}-generation-{dir_item['direction_id']}",
            workflow_id=workflow_id,
        )

        persist_generation_scratchpad_to_blackboard(
            brand_dir,
            profile,
            identity,
            scratchpad_payload,
            output_path=scratchpad_path,
            workflow_id=workflow_id,
        )

        scratchpad_payload["_scratchpad_path"] = str(scratchpad_path)

        # 4. Enforce pre_paid_generation approval trigger
        trigger = next((t for t in policy.approval_triggers if t.name == "pre_paid_generation"), None)
        if trigger:
            from brand_gen.harness.approvals import ApprovalRequest, request_approval
            ticket_id = f"tkt_{uuid.uuid4().hex[:8]}"
            req = ApprovalRequest(
                ticket_id=ticket_id,
                trigger_name="pre_paid_generation",
                run_id=workflow_id,
                campaign_id=campaign_id,
                cost_estimate=1.0,
                description=f"Generate '{material_type}' for direction '{dir_item['name']}' using prompt: {dir_item['physical_prompt'][:60]}...",
            )
            approved = request_approval(brand_dir, req, trigger.mode)
            if not approved:
                raise RuntimeError(f"Approval for paid generation was rejected or suspended in mode {trigger.mode}.")

        # Log generation started
        event_pre_gen = RunEvent(
            stage="generate",
            event_type="generation_started",
            material_type=material_type,
            mode=scratchpad_payload.get("workflow_mode", "hybrid"),
            branch_id=workflow_id,
            parent_branch_id=parent_branch_id,
            model=chosen_model,
            prompt_hash=str(hash(dir_item["physical_prompt"])),
            notes=f"Starting generation for direction '{dir_item['name']}'",
        )
        session.log_event(event_pre_gen)

        # Execute the generation asynchronously in a thread executor
        start_time = time.time()
        loop = asyncio.get_running_loop()
        if str(scratchpad_payload.get("render_backend") or "").strip().lower() == "html":
            version_id = await loop.run_in_executor(
                None,
                lambda: execute_html_share_card_scratchpad(scratchpad_payload, workflow_id=workflow_id)
            )
        else:
            version_id = await loop.run_in_executor(
                None,
                lambda: execute_generation_scratchpad(scratchpad_payload, workflow_id=workflow_id)
            )
        duration_ms = int((time.time() - start_time) * 1000)

        manifest = load_manifest(brand_dir)
        entry = manifest.get("versions", {}).get(version_id, {})
        image_paths = [
            str((brand_dir / name).resolve())
            for name in (entry.get("files") or [])
            if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS and (brand_dir / name).exists()
        ]
        image_path = Path(image_paths[0]) if image_paths else None

        text_details = {
            "headline": scratchpad_payload.get("headline") or plan_dict.get("headline") or "",
            "subhead": scratchpad_payload.get("subhead") or plan_dict.get("subhead") or "",
            "cta": scratchpad_payload.get("cta") or plan_dict.get("cta") or "",
            "proof_title": scratchpad_payload.get("proof_title") or plan_dict.get("proof_title") or "",
            "proof_excerpt": scratchpad_payload.get("proof_excerpt") or plan_dict.get("proof_excerpt") or "",
            "proof_row": scratchpad_payload.get("proof_row") or plan_dict.get("proof_row") or "",
            "proof_meta": scratchpad_payload.get("proof_meta") or plan_dict.get("proof_meta") or [],
        }

        # Validate artifact via capability plugin if registered
        warnings = []
        if capability is not None and image_path is not None:
            try:
                validation_errors = capability.validate_artifact(str(image_path), {
                    "brand_dir": brand_dir,
                    "plan_dict": plan_dict,
                    "scratchpad_payload": scratchpad_payload,
                })
                warnings = [str(e) for e in validation_errors]
            except Exception as exc:
                print(f"Warning: Failed to run capability validation: {exc}")

        # Run deterministic hard constraints checks
        try:
            from brand_gen.harness.critique.rubric import check_hard_constraints
            metadata = {
                "model": chosen_model,
                "expected_aspect_ratio": capability.default_aspect_ratio if capability else "1:1",
            }
            rubric_res = check_hard_constraints(
                brand_dir=brand_dir,
                material_type=material_type,
                generation_prompt=dir_item["physical_prompt"],
                text_details=text_details,
                policy=policy,
                metadata=metadata,
            )
            if not rubric_res["passed"]:
                warnings.extend(rubric_res["blocking_failures"])
        except Exception as exc:
            print(f"Warning: Failed to run hard constraints: {exc}")

        # Log generation completed
        event_post_gen = RunEvent(
            stage="generate",
            event_type="generation_completed",
            material_type=material_type,
            mode=scratchpad_payload.get("workflow_mode", "hybrid"),
            branch_id=workflow_id,
            parent_branch_id=parent_branch_id,
            model=chosen_model,
            output_version=version_id,
            duration_ms=duration_ms,
            notes=f"Generation completed for version {version_id}",
            warnings=warnings,
        )
        session.log_event(event_post_gen)

        # 5. Concurrent Critique Panel
        critic_ids = capability.critic_overrides if capability is not None else None

        from brand_gen.harness.critique.panel import run_critic_panel
        critics_results = await run_critic_panel(
            lm=lm,
            image_path=image_path,
            material_type=material_type,
            generation_prompt=dir_item["physical_prompt"],
            text_details=text_details,
            critic_ids=critic_ids,
        )

        event_critique = RunEvent(
            stage="review",
            event_type="critique_completed",
            material_type=material_type,
            branch_id=workflow_id,
            output_version=version_id,
            notes=f"Critique panel completed for version {version_id}",
            data={"critics_results": critics_results},
        )
        session.log_event(event_critique)

        return {
            "direction_id": dir_item["direction_id"],
            "name": dir_item["name"],
            "version_id": version_id,
            "image_paths": image_paths,
            "image_path": image_path,
            "critics_results": critics_results,
            "scratchpad_path": scratchpad_path,
            "plan_draft_path": plan_draft_path,
            "entry": entry,
        }

    # Execute all directions concurrently
    generation_tasks = [execute_generation_for_direction(d, i) for i, d in enumerate(directions_with_prompts)]
    execution_results = await asyncio.gather(*generation_tasks)

    # 6. Select the best performing result and run the Synthesizer
    best_result = execution_results[0]
    if len(execution_results) > 1:
        def avg_score(res):
            critics = res["critics_results"]
            if not critics:
                return 0
            return sum(c["score"] for c in critics) / len(critics)
        best_result = max(execution_results, key=avg_score)

    from brand_gen.harness.dossier import run_synthesizer_agent, write_dossier
    synthesis = await run_synthesizer_agent(
        lm=lm,
        material_type=material_type,
        creative_brief=creative_brief,
        critics_results=best_result["critics_results"],
    )

    # Write Dossier canonically to reviews/
    json_dossier_path, md_dossier_path = write_dossier(
        brand_dir=brand_dir,
        run_id=workflow_id,
        campaign_id=campaign_id,
        version_id=best_result["version_id"],
        material_type=material_type,
        creative_brief=creative_brief,
        critics_results=best_result["critics_results"],
        synthesis=synthesis,
    )

    event_synthesis = RunEvent(
        stage="review",
        event_type="dossier_written",
        material_type=material_type,
        branch_id=workflow_id,
        output_version=best_result["version_id"],
        notes=f"Synthesized campaign dossier written to {md_dossier_path.name}",
        data={
            "dossier_json": str(json_dossier_path),
            "dossier_md": str(md_dossier_path),
            "synthesis": synthesis,
        },
    )
    session.log_event(event_synthesis)

    # Log campaign completion
    event_end = RunEvent(
        stage="orchestration",
        event_type="campaign_completed",
        material_type=material_type,
        branch_id=workflow_id,
        parent_branch_id=parent_branch_id,
        status="ok",
        notes="Campaign harness run completed successfully",
    )
    session.log_event(event_end)

    stages_completed = ["prepare", "plan", "validate", "execute", "review"]

    return OrchestrateMaterialResponse(
        run_id=workflow_id,
        stages_completed=stages_completed,
        stop_reason=synthesis["recommendation"],
        next_action=None,
        artifacts={
            "plan": str(best_result["plan_draft_path"]),
            "critique": str(json_dossier_path),
            "scratchpad": str(best_result["scratchpad_path"]),
            "version_id": best_result["version_id"],
            "review_packet": str(md_dossier_path),
            "auto_review": str(json_dossier_path),
        },
    )
