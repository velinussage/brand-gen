"""In-process pipeline runner for brand-gen's generative path."""

from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from .pipeline_request import PipelineRequest
    from .pipeline_types import (
        CritiqueChecks,
        GenerationResult,
        GenerationScratchpad,
        PlanCritique,
        PipelineResult,
        PlanDraft,
        RouteDecision,
        RoutingBrief,
        VLMCritique,
        WorkflowMeta,
        critique_from_dict,
        plan_draft_from_dict,
        scratchpad_from_dict,
    )
    from .run_ledger import append_run_event
    from .generation_flow import (
        apply_generation_critique_policy,
        assemble_generation_scratchpad,
        execute_generation_scratchpad,
    )
    from .html_share_cards import execute_html_share_card_scratchpad
    from .material_planning import (
        build_material_plan_from_args,
        build_plan_critique_payload,
        load_plan_payload,
    )
    from .runtime import (
        SUPPORTED_IMAGE_EXTS,
        append_blackboard_decision,
        load_blackboard,
        load_brand_memory,
        load_json_file,
        load_manifest,
        load_pipeline_config,
        persist_generation_scratchpad_to_blackboard,
        persist_plan_critique_to_blackboard,
        persist_plan_draft_to_blackboard,
        role_pack_material_key,
        save_blackboard,
        save_generation_scratchpad,
        save_manifest,
        save_plan_critique,
        save_plan_draft,
        warn,
    )
    from .vlm_critique import refine_prompt_from_vlm_critique, run_vlm_critique
    from .generation_flow import auto_capture_vlm_feedback
except ImportError:  # pragma: no cover - top-level compatibility for direct imports
    from pipeline_request import PipelineRequest  # type: ignore
    from pipeline_types import (  # type: ignore
        CritiqueChecks,
        GenerationResult,
        GenerationScratchpad,
        PlanCritique,
        PipelineResult,
        PlanDraft,
        RouteDecision,
        RoutingBrief,
        VLMCritique,
        WorkflowMeta,
        critique_from_dict,
        plan_draft_from_dict,
        scratchpad_from_dict,
    )
    from run_ledger import append_run_event  # type: ignore
    from generation_flow import (  # type: ignore
        apply_generation_critique_policy,
        assemble_generation_scratchpad,
        execute_generation_scratchpad,
    )
    from html_share_cards import execute_html_share_card_scratchpad  # type: ignore
    from material_planning import (  # type: ignore
        build_material_plan_from_args,
        build_plan_critique_payload,
        load_plan_payload,
    )
    from runtime import (  # type: ignore
        SUPPORTED_IMAGE_EXTS,
        append_blackboard_decision,
        load_blackboard,
        load_brand_memory,
        load_json_file,
        load_manifest,
        load_pipeline_config,
        persist_generation_scratchpad_to_blackboard,
        persist_plan_critique_to_blackboard,
        persist_plan_draft_to_blackboard,
        role_pack_material_key,
        save_blackboard,
        save_generation_scratchpad,
        save_manifest,
        save_plan_critique,
        save_plan_draft,
        warn,
    )
    from vlm_critique import refine_prompt_from_vlm_critique, run_vlm_critique  # type: ignore
    from generation_flow import auto_capture_vlm_feedback  # type: ignore


@dataclass
class StageResult:
    output: Any
    proceed: bool = True
    reason: str = ""


class PipelineRunner:
    """Runs route → plan_draft → critique → scratchpad → generate."""

    def __init__(
        self,
        brand_dir: Path,
        profile: dict,
        identity: dict,
        *,
        max_iterations: int = 1,
        skip_vlm: bool = False,
        use_internal_vlm_critique: bool = False,
        max_retries: int = 1,
        skip_route: bool = False,
        critique_mode: str = "strict",
        allow_blocking: bool = False,
        on_stage_complete: Callable[[str, Any], None] | None = None,
        source_version: str | None = None,
        route_override: str | None = None,
    ):
        self.brand_dir = Path(brand_dir).expanduser().resolve()
        self.profile = profile
        self.identity = identity
        self.max_retries = max(max_retries, 0)
        self._retry_count = 0
        _iter_cfg = load_pipeline_config().get("max_iterations", {})
        _hard_cap = int(_iter_cfg.get("hard_cap", 3))
        self.max_iterations = min(max(max_iterations, 1), _hard_cap)
        self.skip_vlm = skip_vlm
        self.use_internal_vlm_critique = bool(use_internal_vlm_critique) and not bool(skip_vlm)
        self.skip_route = skip_route
        self.critique_mode = "advisory" if str(critique_mode or "").strip().lower() == "advisory" else "strict"
        self.allow_blocking = allow_blocking
        self.on_stage_complete = on_stage_complete
        self.source_version = str(source_version or "").strip()
        self.route_override = str(route_override or "").strip()
        self.workflow_id = uuid.uuid4().hex[:12]
        self.pipeline_request: PipelineRequest | None = None

    def run(self, plan_args: argparse.Namespace) -> PipelineResult:
        self.pipeline_request = PipelineRequest.from_namespace(plan_args)
        plan_args = self.pipeline_request.to_namespace()
        result = PipelineResult(
            workflow_id=self.workflow_id,
            source_version=self.source_version,
            branch_id=self.workflow_id,
        )

        # Derive parent_branch_id from source_version's branch_id if available
        parent_branch_id = ""
        if self.source_version:
            try:
                manifest = load_manifest(self.brand_dir)
                source_entry = manifest.get("versions", {}).get(self.source_version) or {}
                parent_branch_id = source_entry.get("branch_id") or source_entry.get("workflow_id") or ""
            except Exception as exc:
                warn(f"Failed to resolve lineage for {self.source_version}: {exc}")

        # Inject branch metadata so it flows through plan → scratchpad → generation
        if not hasattr(plan_args, "source_version"):
            plan_args.source_version = self.source_version
        if not hasattr(plan_args, "branch_id"):
            plan_args.branch_id = self.workflow_id
        if not hasattr(plan_args, "parent_branch_id"):
            plan_args.parent_branch_id = parent_branch_id

        if not self.skip_route:
            try:
                route_result = self._run_route(plan_args)
                result.route = route_result.output
                if result.route is not None:
                    self._notify("route", result.route)
            except Exception as exc:
                print(f"route_warning: {exc}")

        # Pre-gen Stage 1: Check learnings and apply model/mode preferences
        try:
            self._apply_learnings(plan_args)
        except Exception as exc:
            print(f"pre_gen_learnings_warning: {exc}")

        # Pre-gen Stage 2: Ensure inspiration is extracted (if not already)
        try:
            self._ensure_inspiration(plan_args)
        except Exception as exc:
            print(f"pre_gen_inspiration_warning: {exc}")

        try:
            draft_result = self._run_plan_draft(plan_args)
        except Exception as exc:
            result.stopped_at = "plan_draft"
            result.stop_reason = f"Exception: {exc}"
            return result
        result.plan_draft = draft_result.output
        self._notify("plan_draft", result.plan_draft)
        if not draft_result.proceed:
            result.stopped_at = "plan_draft"
            result.stop_reason = draft_result.reason
            return result

        try:
            critique_result = self._run_critique(result.plan_draft)
        except Exception as exc:
            result.stopped_at = "critique"
            result.stop_reason = f"Exception: {exc}"
            return result
        result.critique = critique_result.output
        self._notify("critique", result.critique)
        if not critique_result.proceed:
            result.stopped_at = "critique"
            result.stop_reason = critique_result.reason
            return result

        try:
            scratchpad_result = self._run_scratchpad(result.plan_draft, result.critique)
        except Exception as exc:
            result.stopped_at = "scratchpad"
            result.stop_reason = f"Exception: {exc}"
            return result
        result.scratchpad = scratchpad_result.output
        self._notify("scratchpad", result.scratchpad)
        if not scratchpad_result.proceed:
            result.stopped_at = "scratchpad"
            result.stop_reason = scratchpad_result.reason
            return result

        try:
            gen_result = self._run_generate(result.scratchpad)
        except Exception as exc:
            result.stopped_at = "generate"
            result.stop_reason = f"Exception: {exc}"
            return result
        result.result = gen_result.output
        result.iterations = result.result.iteration if result.result else 1
        self._notify("generate", result.result)
        if not gen_result.proceed:
            result.stopped_at = "generate"
            result.stop_reason = gen_result.reason
            return result

        # Post-gen: Auto-review and quality gate
        if gen_result.output and gen_result.output.version_id:
            try:
                quality = self._run_quality_gate(gen_result.output)
                result._quality_gate = quality

                # Auto-retry if quality is very low and we haven't exhausted retries
                if quality.get("auto_retry") and self._retry_count < self.max_retries:
                    self._retry_count += 1
                    self._record_iteration_learning(gen_result.output, quality)
                    plan_args.source_version = gen_result.output.version_id
                    return self.run(plan_args)  # Recursive retry
            except Exception as exc:
                print(f"quality_gate_warning: {exc}")

        result.stopped_at = "complete"
        result.stop_reason = "Pipeline completed successfully"
        return result

    def _run_route(self, plan_args: argparse.Namespace) -> StageResult:
        try:
            try:
                from .route_predicates import route_brief
            except ImportError:  # pragma: no cover - top-level compatibility
                from route_predicates import route_brief  # type: ignore
        except ImportError:
            return StageResult(output=None, proceed=True, reason="routing module not available")

        brief = RoutingBrief(
            material_type=getattr(plan_args, "material_type", None),
            material_key=role_pack_material_key(getattr(plan_args, "material_type", None)),
            goal=getattr(plan_args, "goal", "") or "",
            request=getattr(plan_args, "request", "") or "",
            render_backend=getattr(plan_args, "render_backend", "native") or "native",
            source_url=getattr(plan_args, "source_url", "") or "",
            entity_type=getattr(plan_args, "entity_type", "") or "",
            has_motion_reference=bool(getattr(plan_args, "motion_reference", None)),
            set_scope=bool(getattr(plan_args, "set_scope", False)),
            reference_image_count=0,
            mode=getattr(plan_args, "mode", None),
        )
        route_dict = route_brief(brief)
        typed = RouteDecision(
            meta=WorkflowMeta(workflow_id=self.workflow_id, stage="route"),
            route_key=route_dict.get("route_key", "generative_explore"),
            route_label=((route_dict.get("route") or {}).get("label") or ""),
            score=float(route_dict.get("score", 0.0) or 0.0),
            method=str(route_dict.get("method", "default")),
            score_vector=dict(route_dict.get("score_vector") or {}),
            specialists=list(((route_dict.get("route") or {}).get("specialists") or [])),
            next_commands=list(((route_dict.get("route") or {}).get("next_commands") or [])),
            notes=str(((route_dict.get("route") or {}).get("notes") or "")),
        )
        # Apply route override if set and different from recommended
        recommended_route = typed.route_key
        override_reason = ""
        override_actor = ""
        if self.route_override and self.route_override != recommended_route:
            typed = RouteDecision(
                meta=typed.meta,
                route_key=self.route_override,
                route_label=self.route_override,
                score=typed.score,
                method="user_override",
                score_vector=typed.score_vector,
                specialists=typed.specialists,
                next_commands=typed.next_commands,
                notes=f"Override: {recommended_route} -> {self.route_override}",
            )
            override_reason = "user_explicit"
            override_actor = "agent"

        try:
            board = load_blackboard(self.brand_dir, self.profile, self.identity)
            decision_msg = f"Pipeline routed {brief.material_type or 'brand material'} to {typed.route_key}."
            if override_reason:
                decision_msg += f" [OVERRIDE: {recommended_route} -> {typed.route_key}]"
            append_blackboard_decision(
                board,
                agent="brand_director",
                decision=decision_msg,
                confidence=typed.score,
                workflow_id=self.workflow_id,
                data={"route_key": typed.route_key, "recommended_route": recommended_route, "score_vector": typed.score_vector, "method": typed.method, "override_reason": override_reason},
            )
            save_blackboard(self.brand_dir, board)
        except Exception as exc:
            warn(f"Failed to persist routing decision to blackboard: {exc}")
        append_run_event(
            self.brand_dir,
            self.workflow_id,
            stage="route",
            event_type="route_selected",
            material_type=brief.material_type,
            mode=brief.mode,
            recommended_route=recommended_route,
            chosen_route=typed.route_key,
            route_scores=typed.score_vector,
            status="ok",
            notes=typed.method,
            override_reason=override_reason,
            override_actor=override_actor,
            branch_id=self.workflow_id,
        )
        return StageResult(output=typed)

    def _run_plan_draft(self, plan_args: argparse.Namespace) -> StageResult:
        _, plan_dict, missing = build_material_plan_from_args(plan_args, self.brand_dir)
        draft_dict = {
            "schema_type": "plan_draft",
            "schema_version": 1,
            "workflow_id": self.workflow_id,
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
        output_path = save_plan_draft(
            self.brand_dir,
            draft_dict,
            label=f"{plan_dict.get('material_type', 'material')}-{plan_dict.get('mode', 'mode')}-plan-draft",
            workflow_id=self.workflow_id,
        )
        persist_plan_draft_to_blackboard(
            self.brand_dir,
            self.profile,
            self.identity,
            draft_dict,
            output_path=output_path,
            workflow_id=self.workflow_id,
        )
        append_run_event(
            self.brand_dir,
            self.workflow_id,
            stage="plan_draft",
            event_type="plan_drafted",
            material_type=plan_dict.get("material_type"),
            mode=plan_dict.get("mode"),
            selected_reference_paths=[str(item.get("path") or "") for item in ((plan_dict.get("role_pack") or {}).get("selected_roles") or [])],
            selected_reference_ids=list(plan_dict.get("selected_reference_ids") or []),
            status="ok",
            data={"output_path": str(output_path), "missing_required_roles": missing},
        )
        typed = plan_draft_from_dict(draft_dict, self.workflow_id)
        typed.output_path = str(output_path)
        errors = typed.plan.validate()
        if errors:
            return StageResult(output=typed, proceed=False, reason="; ".join(errors))
        return StageResult(output=typed)

    def _critique_args(self, plan_path: str) -> argparse.Namespace:
        return PipelineRequest.build_critique_namespace(
            plan_path,
            critique_mode=self.critique_mode,
            allow_blocking=self.allow_blocking,
            base_image=(self.pipeline_request.base_image if self.pipeline_request else None),
        )

    def _scratchpad_args(self, plan_path: str, plan: dict) -> argparse.Namespace:
        return PipelineRequest.build_scratchpad_namespace(
            plan_path,
            plan,
            critique_mode=self.critique_mode,
            allow_blocking=self.allow_blocking,
            source_version=self.source_version,
            base_image=(self.pipeline_request.base_image if self.pipeline_request else None),
            tag=(self.pipeline_request.tag if self.pipeline_request else None),
            render_backend=(self.pipeline_request.render_backend if self.pipeline_request else "native"),
            source_url=(self.pipeline_request.source_url if self.pipeline_request else None),
            entity_type=(self.pipeline_request.entity_type if self.pipeline_request else None),
            headline=(self.pipeline_request.headline if self.pipeline_request else None),
            subhead=(self.pipeline_request.subhead if self.pipeline_request else None),
            cta=(self.pipeline_request.cta if self.pipeline_request else None),
            proof_title=(self.pipeline_request.proof_title if self.pipeline_request else None),
            proof_excerpt=(self.pipeline_request.proof_excerpt if self.pipeline_request else None),
            proof_row=(self.pipeline_request.proof_row if self.pipeline_request else None),
            proof_meta=(self.pipeline_request.proof_meta if self.pipeline_request else None),
            proof_crop_path=(self.pipeline_request.proof_crop_path if self.pipeline_request else None),
            design_variance=(self.pipeline_request.design_variance if self.pipeline_request else 5),
            layout_spec=(self.pipeline_request.layout_spec if self.pipeline_request else None),
            skip_proof=(self.pipeline_request.skip_proof if self.pipeline_request else False),
            dark_mode=(self.pipeline_request.dark_mode if self.pipeline_request else False),
            branch_id=self.workflow_id,
            parent_branch_id="",
        )

    def _run_critique(self, draft: PlanDraft) -> StageResult:
        wrapper, plan = load_plan_payload(Path(draft.output_path))
        args = self._critique_args(draft.output_path)
        critique_dict = build_plan_critique_payload(
            args,
            brand_dir=self.brand_dir,
            wrapper=wrapper,
            plan=plan,
            critique_mode=self.critique_mode,
            entrypoint="pipeline",
            allow_blocking=self.allow_blocking,
        )
        critique_dict["workflow_id"] = self.workflow_id
        output_path = save_plan_critique(
            self.brand_dir,
            critique_dict,
            label=f"{plan.get('material_type', 'material')}-{plan.get('mode', 'mode')}-critique",
            workflow_id=self.workflow_id,
        )
        persist_plan_critique_to_blackboard(
            self.brand_dir,
            self.profile,
            self.identity,
            critique_dict,
            output_path=output_path,
            workflow_id=self.workflow_id,
        )
        typed = critique_from_dict(critique_dict, self.workflow_id)
        typed.output_path = str(output_path)
        append_run_event(
            self.brand_dir,
            self.workflow_id,
            stage="critique",
            event_type="plan_critiqued",
            material_type=plan.get("material_type"),
            mode=plan.get("mode"),
            status="blocked" if typed.has_blocking else "ok",
            notes=(critique_dict.get("next_step") or ""),
            warnings=list(typed.checks.warnings or []),
            data={
                "blocking": list(typed.checks.blocking or []),
                "output_path": str(output_path),
                "critique_policy": dict(typed.critique_policy or {}),
            },
        )
        if typed.has_blocking and (typed.critique_policy or {}).get("blocks_generation", True):
            return StageResult(output=typed, proceed=False, reason="; ".join(typed.checks.blocking[:3]))
        return StageResult(output=typed)

    def _run_scratchpad(self, draft: PlanDraft, _critique: PlanCritique) -> StageResult:
        wrapper, plan = load_plan_payload(Path(draft.output_path))
        args = self._scratchpad_args(draft.output_path, plan)
        payload = assemble_generation_scratchpad(args, brand_dir=self.brand_dir, plan_wrapper=wrapper, plan=plan)
        payload["workflow_id"] = self.workflow_id
        payload["plan_critique"] = {
            "plan_validation": {
                "ok": _critique.plan_validation.ok,
                "errors": list(_critique.plan_validation.errors),
                "warnings": list(_critique.plan_validation.warnings),
            },
            "prompt_review": {
                "issues": list(_critique.prompt_review.issues),
                "recommendations": list(_critique.prompt_review.recommendations),
            },
            "checks": {
                "blocking": list(_critique.checks.blocking),
                "warnings": list(_critique.checks.warnings),
            },
            "plan_path": _critique.plan_path,
            "output_path": _critique.output_path,
            "critique_policy": dict(_critique.critique_policy or {}),
        }
        checks = payload.setdefault("checks", {})
        checks["blocking"] = list(dict.fromkeys(list(checks.get("blocking") or []) + list(_critique.checks.blocking or [])))
        checks["warnings"] = list(dict.fromkeys(list(checks.get("warnings") or []) + list(_critique.checks.warnings or [])))
        apply_generation_critique_policy(
            payload,
            entrypoint="pipeline",
            critique_mode=self.critique_mode,
            allow_blocking=self.allow_blocking,
        )
        output_path = save_generation_scratchpad(
            self.brand_dir,
            payload,
            label=f"{payload.get('material_type', 'material')}-{payload.get('workflow_mode', 'mode')}-generation",
            workflow_id=self.workflow_id,
        )
        persist_generation_scratchpad_to_blackboard(
            self.brand_dir,
            self.profile,
            self.identity,
            payload,
            output_path=output_path,
            workflow_id=self.workflow_id,
        )
        typed = scratchpad_from_dict(payload, self.workflow_id)
        typed.output_path = str(output_path)
        append_run_event(
            self.brand_dir,
            self.workflow_id,
            stage="scratchpad",
            event_type="scratchpad_built",
            material_type=payload.get("material_type"),
            mode=payload.get("workflow_mode"),
            selected_reference_paths=list((payload.get("reference_context") or {}).get("authoritative_reference_paths") or []),
            selected_reference_ids=list(payload.get("selected_reference_ids") or []) + list(payload.get("selected_inspiration_ids") or []),
            model=((payload.get("execution") or {}).get("model") or ""),
            prompt=payload.get("execution_prompt") or payload.get("effective_prompt") or "",
            status="blocked" if typed.has_blocking else "ok",
            warnings=list(typed.checks.warnings or []),
            data={
                "output_path": str(output_path),
                "critique_policy": dict(typed.critique_policy or {}),
                "reference_analysis_mode": payload.get("reference_analysis_mode") or "",
                "reference_analysis_confidence": payload.get("reference_analysis_confidence") or "",
            },
        )
        if typed.has_blocking and (typed.critique_policy or {}).get("blocks_generation", True):
            return StageResult(output=typed, proceed=False, reason="; ".join(typed.checks.blocking[:3]))
        return StageResult(output=typed)

    def _run_generate(self, scratchpad: GenerationScratchpad) -> StageResult:
        """Generate a brand material version.

        Visual critique is now separate from deterministic generation QA.
        By default the pipeline generates without any internal image-review call.
        The preferred workflow is:
          1. Pipeline generates without ``use_internal_vlm_critique``
          2. Agent reads the image via ``critique-rubric``
          3. Agent evaluates and calls ``submit-critique``
          4. If not approved, agent refines and re-generates

        The legacy internal VLM path remains available only as an explicit
        opt-in via ``use_internal_vlm_critique``.
        """
        payload = load_json_file(Path(scratchpad.output_path))
        payload["_scratchpad_path"] = scratchpad.output_path
        if str(payload.get("render_backend") or "").strip().lower() == "html":
            version_id = execute_html_share_card_scratchpad(payload, workflow_id=self.workflow_id)
            manifest = load_manifest(self.brand_dir)
            entry = manifest["versions"].get(version_id, {})
            image_paths = [str(Path(self.brand_dir) / name) for name in (entry.get("files") or []) if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS]
            result = GenerationResult(
                meta=WorkflowMeta(workflow_id=self.workflow_id, stage="generate"),
                version_id=version_id,
                image_paths=image_paths,
                scratchpad_path=scratchpad.output_path,
                auto_review_path=str(entry.get("auto_review_path") or ""),
                agent_review_path=str(entry.get("agent_review_path") or ""),
                critique_policy=dict(entry.get("critique_policy") or payload.get("critique_policy") or {}),
                visual_review_status=str(entry.get("visual_review_status") or "pending"),
                iteration=1,
                all_versions=[version_id],
            )
            return StageResult(output=result)
        all_versions: list[str] = []
        final_vlm: dict[str, Any] | None = None
        current_payload = payload
        for iteration in range(self.max_iterations):
            version_id = execute_generation_scratchpad(current_payload, workflow_id=self.workflow_id)
            all_versions.append(version_id)
            if not self.use_internal_vlm_critique:
                break

            # Legacy fallback: internal VLM critique (deprecated and opt-in only;
            # agents should use critique-rubric + submit-critique instead)
            brand_dir = Path(current_payload["brand_dir"]).expanduser().resolve()
            manifest = load_manifest(brand_dir)
            entry = manifest["versions"].get(version_id, {})
            image_files = [brand_dir / name for name in (entry.get("files") or []) if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS]
            if not image_files or not image_files[0].exists():
                break
            board = load_blackboard(brand_dir)
            final_vlm = run_vlm_critique(
                image_files[0],
                current_payload.get("execution_prompt") or current_payload.get("effective_prompt") or "",
                board.get("brand_dna") or {},
            )
            if not final_vlm.get("vlm_available"):
                break
            if final_vlm.get("approved"):
                break
            if iteration >= self.max_iterations - 1:
                break
            refined_prompt = refine_prompt_from_vlm_critique(
                current_payload.get("execution_prompt") or current_payload.get("effective_prompt") or "",
                final_vlm,
            )
            next_payload = dict(current_payload)
            next_payload["execution_prompt"] = refined_prompt
            if not next_payload.get("effective_prompt"):
                next_payload["effective_prompt"] = refined_prompt
            current_payload = next_payload
            profile_path = current_payload.get("profile_path")
            identity_path = current_payload.get("identity_path")
            _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
            bb = load_blackboard(brand_dir, profile, identity)
            append_blackboard_decision(
                bb,
                agent="critic_agent",
                decision=f"Pipeline VLM critique requested another iteration after {version_id}.",
                confidence=0.85,
                severity="P2",
                workflow_id=self.workflow_id,
                data={"version": version_id},
            )
            save_blackboard(brand_dir, bb)

        manifest = load_manifest(self.brand_dir)
        final_version = all_versions[-1]
        entry = manifest["versions"].get(final_version, {})
        if final_vlm:
            vlm_path = self.brand_dir / "reviews" / f"{final_version}-vlm-critique.json"
            vlm_path.parent.mkdir(parents=True, exist_ok=True)
            vlm_path.write_text(json.dumps(final_vlm, indent=2) + "\n")
            entry["vlm_critique_path"] = str(vlm_path)
            entry["vlm_critique"] = {
                "approved": final_vlm.get("approved", False),
                "p1_count": len(final_vlm.get("p1") or []),
                "p2_count": len(final_vlm.get("p2") or []),
                "palette_match": final_vlm.get("palette_match", 0),
                "logo_visible": final_vlm.get("logo_visible", False),
                "vlm_available": final_vlm.get("vlm_available", False),
                "provider": final_vlm.get("vlm_provider", "internal"),
            }
            entry["visual_review_status"] = "approved" if final_vlm.get("approved", False) else "needs_refinement"
            entry["visual_review_provider"] = final_vlm.get("vlm_provider", "internal")
            manifest["versions"][final_version] = entry
            save_manifest(manifest, self.brand_dir)
            append_run_event(
                self.brand_dir,
                self.workflow_id,
                stage="review",
                event_type="vlm_critique_saved",
                attempt_id=final_version,
                material_type=entry.get("material_type") or current_payload.get("material_type") or "",
                mode=entry.get("mode") or current_payload.get("workflow_mode") or "",
                model=entry.get("model") or ((current_payload.get("execution") or {}).get("model") or ""),
                provider=final_vlm.get("vlm_provider") or "internal",
                output_version=final_version,
                status="approved" if final_vlm.get("approved") else "needs_refinement",
                data={"vlm_critique_path": str(vlm_path), "p1": list(final_vlm.get("p1") or []), "p2_count": len(final_vlm.get("p2") or [])},
            )
            auto_capture_vlm_feedback(self.brand_dir, final_version, entry, final_vlm)
        image_paths = [str(Path(self.brand_dir) / name) for name in (entry.get("files") or []) if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS]
        vlm_typed = None
        if final_vlm:
            vlm_typed = VLMCritique(
                approved=bool(final_vlm.get("approved", False)),
                p1=list(final_vlm.get("p1") or []),
                p2=list(final_vlm.get("p2") or []),
                p3=list(final_vlm.get("p3") or []),
                palette_match=float(final_vlm.get("palette_match", 0.0) or 0.0),
                logo_visible=bool(final_vlm.get("logo_visible", False)),
                hallucinated_elements=list(final_vlm.get("hallucinated_elements") or []),
                refinement_suggestion=str(final_vlm.get("refinement_suggestion") or ""),
                vlm_available=bool(final_vlm.get("vlm_available", False)),
            )
        result = GenerationResult(
            meta=WorkflowMeta(workflow_id=self.workflow_id, stage="generate"),
            version_id=final_version,
            image_paths=image_paths,
            scratchpad_path=scratchpad.output_path,
            auto_review_path=str(entry.get("auto_review_path") or ""),
            agent_review_path=str(entry.get("agent_review_path") or ""),
            critique_policy=dict(entry.get("critique_policy") or current_payload.get("critique_policy") or {}),
            vlm_critique=vlm_typed,
            visual_review_status=str(
                entry.get("visual_review_status")
                or ("approved" if final_vlm and final_vlm.get("approved") else ("needs_refinement" if final_vlm else "pending"))
            ),
            iteration=len(all_versions),
            all_versions=all_versions,
        )
        return StageResult(output=result)

    def _notify(self, stage: str, output: Any) -> None:
        if self.on_stage_complete:
            try:
                self.on_stage_complete(stage, output)
            except Exception as exc:
                warn(f"Pipeline stage callback failed for {stage}: {exc}")

    # ------------------------------------------------------------------
    # Pre-generation helpers
    # ------------------------------------------------------------------

    def _apply_learnings(self, plan_args: argparse.Namespace) -> dict:
        """Read learnings.json and apply model/mode preferences for the material type.

        Parses entries like ``[social] Winning setup: hybrid + html:chromium + without refs``
        from the ``modelPreferences`` bucket and overrides plan_args defaults where
        applicable.  Returns a dict of overrides that were applied (may be empty).
        """
        try:
            from .learnings_memory import load_learnings_memory
        except ImportError:
            from learnings_memory import load_learnings_memory  # type: ignore

        overrides: dict[str, str] = {}
        learnings = load_learnings_memory(self.brand_dir)
        material_type = getattr(plan_args, "material_type", None) or ""
        mat_key = role_pack_material_key(material_type) or material_type or ""

        model_prefs = learnings.get("modelPreferences") or []
        for pref in model_prefs:
            text = str(pref.get("text") if isinstance(pref, dict) else pref).strip()
            if not text:
                continue

            # Match entries like "[social] Winning setup: hybrid + html:chromium + without refs"
            prefix_match = re.match(
                r"^\[([^\]]+)\]\s*Winning setup:\s*(.+)$", text, re.IGNORECASE
            )
            if not prefix_match:
                continue

            entry_key = prefix_match.group(1).strip()
            if entry_key.lower() != mat_key.lower():
                continue

            setup_parts = [p.strip() for p in prefix_match.group(2).split("+")]
            for part in setup_parts:
                part_lower = part.lower()
                # Mode override (e.g. "hybrid", "reference", "inspiration")
                if part_lower in {"hybrid", "reference", "inspiration"}:
                    if not getattr(plan_args, "mode", None) or getattr(plan_args, "mode", "") == "auto":
                        plan_args.mode = part_lower
                        overrides["mode"] = part_lower
                # Render backend hint (e.g. "html:chromium", "native")
                elif part_lower.startswith("html"):
                    if not getattr(plan_args, "render_backend", None) or getattr(plan_args, "render_backend", "") == "native":
                        plan_args.render_backend = "html"
                        overrides["render_backend"] = "html"

        if overrides:
            print(f"pre_gen_learnings: applied overrides from learnings.json: {overrides}")
        return overrides

    def _ensure_inspiration(self, plan_args: argparse.Namespace) -> None:
        """Check if inspiration sources are configured but not extracted and attempt extraction.

        This is best-effort: all exceptions are caught, logged, and the pipeline
        continues regardless of success or failure.
        """
        try:
            from .runtime_brand import (
                get_brand_gen_dir,
                load_inspiration_index,
                load_inspirations_config,
                resolve_context_brand_key,
            )
        except ImportError:
            from runtime_brand import (  # type: ignore
                get_brand_gen_dir,
                load_inspiration_index,
                load_inspirations_config,
                resolve_context_brand_key,
            )

        brand_gen_dir = get_brand_gen_dir()
        if not brand_gen_dir or not brand_gen_dir.exists():
            return

        active_brand = resolve_context_brand_key(
            brand_dir=self.brand_dir,
            profile=self.profile,
            identity=self.identity,
            brand_gen_dir=brand_gen_dir,
        ) or self.brand_dir.name
        config = load_inspirations_config(active_brand, brand_gen_dir)
        sources = config.get("sources") or []
        if not sources:
            return

        index = load_inspiration_index(brand_gen_dir).get("sources", {})
        unextracted = [s for s in sources if s in index and index[s].get("status") != "complete"]
        if not unextracted:
            return

        print(f"pre_gen_inspiration: {len(unextracted)} source(s) not fully extracted, attempting extraction")
        try:
            material_type = getattr(plan_args, "material_type", None) or ""
            extract_args = argparse.Namespace(
                workers=2,
                timeout=30,
                category=material_type or None,
                limit=None,
                force=False,
                source=unextracted[:3],
            )
            try:
                from .commands.references import cmd_extract_inspiration
            except ImportError:
                from commands.references import cmd_extract_inspiration  # type: ignore
            cmd_extract_inspiration(extract_args)
            print(f"pre_gen_inspiration: extraction attempted for {len(unextracted[:3])} source(s)")
        except Exception as exc:
            print(f"pre_gen_inspiration_warning: extraction failed (non-blocking): {exc}")

    # ------------------------------------------------------------------
    # Post-generation quality gate
    # ------------------------------------------------------------------

    def _run_quality_gate(self, gen_result: GenerationResult) -> dict:
        """Run a structural quality check on the generated output.

        Checks that output files exist, are non-empty, and have reasonable size.
        Returns ``{"passed": bool, "auto_retry": bool, "reason": str}``.
        ``auto_retry`` is True only when the output is clearly broken (empty file,
        generation error, missing output).
        """
        version_id = gen_result.version_id
        image_paths = gen_result.image_paths or []

        # Check 1: Do we have any output files at all?
        if not image_paths:
            print(f"quality_gate: FAIL - no output files for {version_id}")
            return {"passed": False, "auto_retry": True, "reason": "No output files produced"}

        # Check 2: Do the files exist and are they non-empty?
        for img_path in image_paths:
            p = Path(img_path)
            if not p.exists():
                print(f"quality_gate: FAIL - output file missing: {p.name}")
                return {"passed": False, "auto_retry": True, "reason": f"Output file missing: {p.name}"}
            size = p.stat().st_size
            if size == 0:
                print(f"quality_gate: FAIL - output file empty: {p.name}")
                return {"passed": False, "auto_retry": True, "reason": f"Output file is empty: {p.name}"}
            # Very small image files (< 1KB) are likely broken
            if size < 1024:
                print(f"quality_gate: WARN - output file suspiciously small ({size}B): {p.name}")
                return {"passed": False, "auto_retry": True, "reason": f"Output file suspiciously small ({size}B): {p.name}"}

        # Check 3: Inspect auto-review if available
        if gen_result.auto_review_path:
            review_path = Path(gen_result.auto_review_path)
            if review_path.exists():
                try:
                    review = json.loads(review_path.read_text())
                    if review.get("error") or review.get("generation_error"):
                        reason = str(review.get("error") or review.get("generation_error"))
                        print(f"quality_gate: FAIL - auto-review reports error: {reason[:120]}")
                        return {"passed": False, "auto_retry": True, "reason": f"Auto-review error: {reason[:120]}"}
                except (json.JSONDecodeError, OSError):
                    pass

        print(f"quality_gate: PASS - {version_id} ({len(image_paths)} file(s))")
        return {"passed": True, "auto_retry": False, "reason": "Structural checks passed"}

    def _record_iteration_learning(self, gen_result: GenerationResult, quality: dict) -> None:
        """Write quality-gate failure info to iteration-memory.json so the next attempt benefits."""
        try:
            from .iteration_memory import load_iteration_memory, save_iteration_memory, add_iteration_note
        except ImportError:
            from iteration_memory import load_iteration_memory, save_iteration_memory, add_iteration_note  # type: ignore

        memory = load_iteration_memory(self.brand_dir)
        reason = quality.get("reason", "Quality gate failure")
        note = f"Pipeline auto-retry after quality failure on {gen_result.version_id}: {reason}"
        memory = add_iteration_note(memory, note, bucket="brand_notes")

        negative_record = {
            "version": gen_result.version_id,
            "material_type": "",
            "summary": f"Quality gate failure: {reason}",
            "score": 1,
            "status": "rejected",
        }
        existing = memory.get("negative_examples", [])
        existing = [item for item in existing if item.get("version") != gen_result.version_id]
        existing.append(negative_record)
        memory["negative_examples"] = existing[-20:]

        save_iteration_memory(self.brand_dir, memory)
        print(f"quality_gate: recorded failure learning for {gen_result.version_id}")
