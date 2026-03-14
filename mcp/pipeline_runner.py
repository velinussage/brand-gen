"""In-process pipeline runner for brand-gen's generative path."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
        skip_route: bool = False,
        on_stage_complete: Callable[[str, Any], None] | None = None,
    ):
        self.brand_dir = Path(brand_dir).expanduser().resolve()
        self.profile = profile
        self.identity = identity
        self.max_iterations = min(max(max_iterations, 1), 3)
        self.skip_vlm = skip_vlm
        self.skip_route = skip_route
        self.on_stage_complete = on_stage_complete
        self.workflow_id = uuid.uuid4().hex[:12]

    def run(self, plan_args: argparse.Namespace) -> PipelineResult:
        result = PipelineResult(workflow_id=self.workflow_id)

        if not self.skip_route:
            try:
                route_result = self._run_route(plan_args)
                result.route = route_result.output
                if result.route is not None:
                    self._notify("route", result.route)
            except Exception as exc:
                print(f"route_warning: {exc}")

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

        result.stopped_at = "complete"
        result.stop_reason = "Pipeline completed successfully"
        return result

    def _run_route(self, plan_args: argparse.Namespace) -> StageResult:
        try:
            from route_predicates import route_brief  # type: ignore
            from brand_iterate import append_blackboard_decision, load_blackboard, role_pack_material_key, save_blackboard  # type: ignore
        except ImportError:
            return StageResult(output=None, proceed=True, reason="routing module not available")

        brief = RoutingBrief(
            material_type=getattr(plan_args, "material_type", None),
            material_key=role_pack_material_key(getattr(plan_args, "material_type", None)),
            goal=getattr(plan_args, "goal", "") or "",
            request=getattr(plan_args, "request", "") or "",
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
        try:
            board = load_blackboard(self.brand_dir, self.profile, self.identity)
            append_blackboard_decision(
                board,
                agent="brand_director",
                decision=f"Pipeline routed {brief.material_type or 'brand material'} to {typed.route_key}.",
                confidence=typed.score,
                workflow_id=self.workflow_id,
                data={"route_key": typed.route_key, "score_vector": typed.score_vector, "method": typed.method},
            )
            save_blackboard(self.brand_dir, board)
        except Exception:
            pass
        return StageResult(output=typed)

    def _run_plan_draft(self, plan_args: argparse.Namespace) -> StageResult:
        from brand_iterate import build_material_plan_from_args, persist_plan_draft_to_blackboard, save_plan_draft  # type: ignore

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
        )
        persist_plan_draft_to_blackboard(
            self.brand_dir,
            self.profile,
            self.identity,
            draft_dict,
            output_path=output_path,
            workflow_id=self.workflow_id,
        )
        typed = plan_draft_from_dict(draft_dict, self.workflow_id)
        typed.output_path = str(output_path)
        errors = typed.plan.validate()
        if errors:
            return StageResult(output=typed, proceed=False, reason="; ".join(errors))
        return StageResult(output=typed)

    def _critique_args(self, plan_path: str) -> argparse.Namespace:
        return argparse.Namespace(
            plan=plan_path,
            prompt=None,
            material_type=None,
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
            profile=None,
            identity=None,
            disable_brand_guardrails=False,
            output=None,
            format="json",
        )

    def _scratchpad_args(self, plan_path: str, plan: dict) -> argparse.Namespace:
        return argparse.Namespace(
            prompt=None,
            plan=plan_path,
            material_type=plan.get("material_type"),
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
            profile=None,
            identity=None,
            disable_brand_guardrails=False,
            skip_extraction=False,
            refresh_reference_analysis=False,
            allow_blocking=False,
            output=None,
            format="json",
        )

    def _run_critique(self, draft: PlanDraft) -> StageResult:
        from brand_iterate import build_plan_critique_payload, load_plan_payload, persist_plan_critique_to_blackboard, save_plan_critique  # type: ignore

        wrapper, plan = load_plan_payload(Path(draft.output_path))
        args = self._critique_args(draft.output_path)
        critique_dict = build_plan_critique_payload(args, brand_dir=self.brand_dir, wrapper=wrapper, plan=plan)
        critique_dict["workflow_id"] = self.workflow_id
        output_path = save_plan_critique(
            self.brand_dir,
            critique_dict,
            label=f"{plan.get('material_type', 'material')}-{plan.get('mode', 'mode')}-critique",
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
        if typed.has_blocking:
            return StageResult(output=typed, proceed=False, reason="; ".join(typed.checks.blocking[:3]))
        return StageResult(output=typed)

    def _run_scratchpad(self, draft: PlanDraft, _critique: PlanCritique) -> StageResult:
        from brand_iterate import assemble_generation_scratchpad, load_plan_payload, persist_generation_scratchpad_to_blackboard, save_generation_scratchpad  # type: ignore

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
        }
        checks = payload.setdefault("checks", {})
        checks["blocking"] = list(dict.fromkeys(list(checks.get("blocking") or []) + list(_critique.checks.blocking or [])))
        checks["warnings"] = list(dict.fromkeys(list(checks.get("warnings") or []) + list(_critique.checks.warnings or [])))
        output_path = save_generation_scratchpad(
            self.brand_dir,
            payload,
            label=f"{payload.get('material_type', 'material')}-{payload.get('workflow_mode', 'mode')}-generation",
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
        if typed.has_blocking:
            return StageResult(output=typed, proceed=False, reason="; ".join(typed.checks.blocking[:3]))
        return StageResult(output=typed)

    def _run_generate(self, scratchpad: GenerationScratchpad) -> StageResult:
        from brand_iterate import (
            SUPPORTED_IMAGE_EXTS,
            execute_generation_scratchpad,
            load_blackboard,
            load_brand_memory,
            load_json_file,
            load_manifest,
            refine_prompt_from_vlm_critique,
            run_vlm_critique,
            save_blackboard,
        )  # type: ignore

        payload = load_json_file(Path(scratchpad.output_path))
        payload["_scratchpad_path"] = scratchpad.output_path
        all_versions: list[str] = []
        final_vlm: dict[str, Any] | None = None
        current_payload = payload
        for iteration in range(self.max_iterations):
            version_id = execute_generation_scratchpad(current_payload, workflow_id=self.workflow_id)
            all_versions.append(version_id)
            if self.skip_vlm:
                break

            brand_dir = Path(current_payload["brand_dir"]).expanduser().resolve()
            manifest = load_manifest()
            entry = manifest["versions"].get(version_id, {})
            image_files = [brand_dir / name for name in (entry.get("files") or []) if Path(name).suffix.lower() in SUPPORTED_IMAGE_EXTS]
            if not image_files or not image_files[0].exists():
                break
            board = load_blackboard(brand_dir)
            final_vlm = run_vlm_critique(image_files[0], current_payload.get("effective_prompt") or "", board.get("brand_dna") or {})
            if not final_vlm.get("vlm_available"):
                break
            if final_vlm.get("approved"):
                break
            if iteration >= self.max_iterations - 1:
                break
            refined_prompt = refine_prompt_from_vlm_critique(current_payload.get("effective_prompt") or "", final_vlm)
            next_payload = dict(current_payload)
            next_payload["effective_prompt"] = refined_prompt
            current_payload = next_payload
            profile_path = current_payload.get("profile_path")
            identity_path = current_payload.get("identity_path")
            _, _, profile, identity = load_brand_memory(brand_dir, profile_path, identity_path)
            bb = load_blackboard(brand_dir, profile, identity)
            from brand_iterate import append_blackboard_decision  # type: ignore

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

        manifest = load_manifest()
        final_version = all_versions[-1]
        entry = manifest["versions"].get(final_version, {})
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
            vlm_critique=vlm_typed,
            iteration=len(all_versions),
            all_versions=all_versions,
        )
        return StageResult(output=result)

    def _notify(self, stage: str, output: Any) -> None:
        if self.on_stage_complete:
            try:
                self.on_stage_complete(stage, output)
            except Exception:
                pass
