from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from brand_gen import brand_iterate_mcp
from brand_gen.command_registry import COMMAND_HANDLERS
from brand_gen.commands import generation as generation_commands
from brand_gen.mcp_bridge_registry import BRIDGE_BY_TOOL, argv_from_mcp_args, build_tool_schema
from brand_gen.pipeline_runner import PipelineRunner, StageResult
from brand_gen.pipeline_types import (
    CritiqueChecks,
    ExecuteRunResponse,
    GenerationResult,
    GenerationScratchpad,
    MaterialPlan,
    OrchestrateMaterialResponse,
    PlanCritique,
    PlanDraft,
    PlanValidation,
    PromptReview,
    RouteDecision,
    WorkflowMeta,
)
from brand_gen.run_ledger import load_all_run_events


class DummyOrchestrationRunner(PipelineRunner):
    def __init__(self, brand_dir: Path):
        super().__init__(brand_dir, {"brand_name": "Acme"}, {"brand": {"name": "Acme"}})
        self.plan_path = brand_dir / "scratchpads" / "plan-drafts" / "draft.json"
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(
            json.dumps(
                {
                    "workflow_id": self.workflow_id,
                    "plan": {"material_type": "social", "mode": "hybrid"},
                    "derived": {
                        "selected_role_names": ["composition"],
                        "missing_required_roles": [],
                    },
                }
            )
        )

    def _apply_learnings(self, plan_args):
        return {"mode": "hybrid"}

    def _ensure_inspiration(self, plan_args):
        return None

    def _run_route(self, plan_args):
        return StageResult(
            RouteDecision(
                meta=WorkflowMeta(self.workflow_id, "route"),
                route_key="generative_explore",
                route_label="Generative explore",
                score=0.8,
                method="predicate",
            )
        )

    def _run_plan_draft(self, plan_args):
        return StageResult(
            PlanDraft(
                meta=WorkflowMeta(self.workflow_id, "plan_draft"),
                plan=MaterialPlan(material_type="social", mode="hybrid", purpose="Launch awareness"),
                derived={"selected_role_names": ["composition"], "missing_required_roles": []},
                output_path=str(self.plan_path),
            )
        )

    def _run_critique(self, draft):
        return StageResult(
            PlanCritique(
                meta=WorkflowMeta(self.workflow_id, "critique"),
                plan_validation=PlanValidation(ok=True),
                prompt_review=PromptReview(issues=[], recommendations=[]),
                checks=CritiqueChecks(blocking=[], warnings=["watch copy density"]),
                critique_policy={"blocks_generation": True},
                output_path=str(self.plan_path.parent.parent / "plan-critiques" / "critique.json"),
            )
        )

    def _run_scratchpad(self, draft, critique):
        return StageResult(
            GenerationScratchpad(
                meta=WorkflowMeta(self.workflow_id, "scratchpad"),
                material_type="social",
                workflow_mode="hybrid",
                effective_prompt="hello",
                output_path=str(self.plan_path.parent.parent / "generation" / "scratch.json"),
            )
        )

    def _run_generate(self, scratchpad):
        return StageResult(
            GenerationResult(
                meta=WorkflowMeta(self.workflow_id, "generate"),
                version_id="v101",
                image_paths=[str(self.brand_dir / "v101.png")],
                scratchpad_path=scratchpad.output_path,
                agent_review_path=str(self.brand_dir / "reviews" / "v101-agent-review.json"),
                auto_review_path=str(self.brand_dir / "reviews" / "v101-auto-review.json"),
                visual_review_status="pending",
                iteration=1,
                all_versions=["v101"],
            )
        )

    def _run_quality_gate(self, gen_result):
        return {"passed": True, "auto_retry": False, "reason": "Structural checks passed"}


class BlockingCritiqueRunner(DummyOrchestrationRunner):
    def _run_critique(self, draft):
        return StageResult(
            PlanCritique(
                meta=WorkflowMeta(self.workflow_id, "critique"),
                plan_validation=PlanValidation(ok=True),
                prompt_review=PromptReview(issues=[], recommendations=[]),
                checks=CritiqueChecks(blocking=["fix copy accuracy"], warnings=[]),
                critique_policy={"blocks_generation": True},
                output_path=str(self.plan_path.parent.parent / "plan-critiques" / "critique.json"),
            ),
            proceed=False,
            reason="fix copy accuracy",
        )


class OrchestrationRunnerTests(unittest.TestCase):
    def test_prepare_run_returns_typed_payload_and_ledger_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            runner = DummyOrchestrationRunner(brand_dir)
            with patch("brand_gen.plan_builder.check_identity_freshness", return_value={"needs_rebuild": False, "reasons": []}), \
                 patch("brand_gen.generation_flow.check_inspiration_pipeline_status", return_value={"ok": True, "warnings": [], "suggestions": []}), \
                 patch("brand_gen.runtime_brand.get_brand_gen_dir", return_value=brand_dir), \
                 patch("brand_gen.runtime_brand.resolve_context_brand_key", return_value="acme"):
                payload = runner.prepare_run(argparse.Namespace(material_type="social", mode="hybrid"))

            self.assertEqual(payload.run_id, runner.workflow_id)
            self.assertEqual(payload.route["route_key"], "generative_explore")
            self.assertEqual(payload.next_action.tool, "brand_plan_run")
            events = load_all_run_events(brand_dir)
            self.assertTrue(any(evt["event_type"] == "prepare_run_completed" for evt in events))

    def test_plan_run_returns_plan_id_and_validate_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = DummyOrchestrationRunner(Path(tmp))
            payload = runner.plan_run(argparse.Namespace(material_type="social", mode="hybrid"))
            self.assertTrue(payload.plan_id.endswith("draft.json"))
            self.assertEqual(payload.plan_summary["selected_role_names"], ["composition"])
            self.assertEqual(payload.next_action.tool, "brand_validate_run")

    def test_validate_run_reports_blocking_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = BlockingCritiqueRunner(Path(tmp))
            payload = runner.validate_run(str(runner.plan_path))
            self.assertEqual(payload.status, "blocked")
            self.assertEqual(payload.blocking_issues, ["fix copy accuracy"])
            self.assertIsNone(payload.next_action)

    def test_validate_run_errors_for_missing_plan_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = DummyOrchestrationRunner(Path(tmp))
            with self.assertRaisesRegex(ValueError, "plan draft not found"):
                runner.validate_run(str(Path(tmp) / "missing.json"))

    def test_execute_run_returns_version_and_review_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "v101.png").write_bytes(b"not-a-real-image-but-large-enough" * 80)
            runner = DummyOrchestrationRunner(brand_dir)
            payload = runner.execute_run(str(runner.plan_path))
            self.assertEqual(payload.version_id, "v101")
            self.assertEqual(payload.stopped_at, "complete")
            self.assertEqual(payload.next_action.tool, "brand_review_run")
            self.assertTrue(payload.quality_gate["passed"])

    def test_execute_run_errors_for_missing_critique_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = DummyOrchestrationRunner(Path(tmp))
            with self.assertRaisesRegex(ValueError, "critique not found"):
                runner.execute_run(str(runner.plan_path), critique_path=str(Path(tmp) / "missing-critique.json"))

    def test_review_run_reads_manifest_review_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "versions": {
                            "v009": {
                                "workflow_id": "wf-009",
                                "agent_review_path": str(brand_dir / "reviews" / "v009-agent-review.json"),
                                "auto_review_path": str(brand_dir / "reviews" / "v009-auto-review.json"),
                                "visual_review_status": "needs_refinement",
                                "vlm_critique": {
                                    "axis_scores": {"brand_fit": 3},
                                    "decision": "needs_refinement",
                                },
                            }
                        }
                    }
                )
            )
            runner = DummyOrchestrationRunner(brand_dir)
            payload = runner.review_run("v009")
            self.assertEqual(payload.run_id, "wf-009")
            self.assertEqual(payload.packet_id, str(brand_dir / "reviews" / "v009-agent-review.json"))
            self.assertEqual(payload.axis_scores["brand_fit"], 3)
            self.assertEqual(payload.next_action.tool, "brand_submit_review")

    def test_evolve_run_surfaces_promotions_questions_and_disagreements(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            (brand_dir / "manifest.json").write_text(
                json.dumps({"versions": {"v010": {"workflow_id": "wf-010", "material_type": "social", "visual_review_status": "approved"}}})
            )
            runner = DummyOrchestrationRunner(brand_dir)
            with patch("brand_gen.learnings_memory.promote_blackboard_lessons_to_learnings", return_value={"promoted": [{"bucket": "failurePatterns", "text": "Avoid cramped copy"}]}), \
                 patch("brand_gen.plan_builder.check_identity_freshness", return_value={"needs_rebuild": False, "reasons": []}), \
                 patch("brand_gen.plan_builder.build_improvement_questions", return_value=[{"question": "What proof mattered?"}]), \
                 patch("brand_gen.scoring.dataset.load_disagreements", return_value=[{"version_id": "v010"}, {"version_id": "v999"}]):
                payload = runner.evolve_run("v010")
            self.assertEqual(len(payload.learnings_promoted), 1)
            self.assertEqual(payload.disagreements_logged, 1)
            self.assertEqual(payload.recommendation, "answer_improvement_questions")

    def test_evolve_run_errors_when_version_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = DummyOrchestrationRunner(Path(tmp))
            with self.assertRaisesRegex(ValueError, "version not found"):
                runner.evolve_run("v404")


class CommandAndBridgeTests(unittest.TestCase):
    def test_chunk_e_commands_registered_for_cli_and_mcp(self):
        for command in [
            "prepare-run",
            "plan-run",
            "validate-run",
            "execute-run",
            "review-run",
            "evolve-run",
            "orchestrate-material",
        ]:
            self.assertIn(command, COMMAND_HANDLERS)
        for tool in [
            "brand_prepare_run",
            "brand_plan_run",
            "brand_validate_run",
            "brand_execute_run",
            "brand_review_run",
            "brand_evolve_run",
            "brand_orchestrate_material",
        ]:
            self.assertIn(tool, BRIDGE_BY_TOOL)

    def test_validate_run_schema_requires_plan_draft(self):
        schema = build_tool_schema(BRIDGE_BY_TOOL["brand_validate_run"])
        self.assertIn("plan_draft", schema.get("required", []))

    def test_prepare_run_layout_spec_schema_and_argv_are_json_safe(self):
        schema = build_tool_schema(BRIDGE_BY_TOOL["brand_prepare_run"])
        self.assertEqual(schema["properties"]["layout_spec"]["type"], "object")
        argv = argv_from_mcp_args(
            BRIDGE_BY_TOOL["brand_prepare_run"],
            {"material_type": "social", "layout_spec": {"columns": 2, "alignment": "left"}},
        )
        self.assertIn("--layout-spec", argv)
        layout_value = argv[argv.index("--layout-spec") + 1]
        self.assertEqual(json.loads(layout_value), {"columns": 2, "alignment": "left"})

    def test_prepare_run_bridge_dispatches_to_cli_command(self):
        with patch("brand_gen.brand_iterate_mcp.run_brand_iterate", return_value=('{"ok":true}', True)) as mocked:
            output, is_error = brand_iterate_mcp.handle_tool_call("brand_prepare_run", {"material_type": "social"})
        self.assertFalse(is_error)
        argv = mocked.call_args.args[0]
        self.assertEqual(argv[0], "prepare-run")
        self.assertIn("--material-type", argv)
        self.assertIn("social", argv)
        self.assertEqual(json.loads(output)["ok"], True)

    def test_orchestrate_material_command_prints_json_payload(self):
        fake_runner = Mock()
        fake_runner.orchestrate_material.return_value = OrchestrateMaterialResponse(
            run_id="wf-123",
            stages_completed=["prepare", "plan"],
            stop_reason="iterating",
        )
        args = argparse.Namespace(material_type="social", mode="hybrid", format="json")
        out = io.StringIO()
        with patch.object(generation_commands, "_build_pipeline_runner_from_request", return_value=(fake_runner, Path("/tmp"), {}, {})), contextlib.redirect_stdout(out):
            generation_commands.cmd_orchestrate_material(args)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["run_id"], "wf-123")
        self.assertEqual(payload["stop_reason"], "iterating")

    def test_execute_run_response_serializes_cleanly(self):
        payload = ExecuteRunResponse(run_id="wf-1", version_id="v1")
        self.assertEqual(payload.to_dict()["version_id"], "v1")


if __name__ == "__main__":
    unittest.main()
