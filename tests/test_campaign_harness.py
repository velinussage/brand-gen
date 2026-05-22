"""Unit tests for the PR-2 campaign runner harness control plane."""

import json
import tempfile
import unittest
import copy
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from brand_gen.pipeline_runner import PipelineRunner
from brand_gen.pipeline_types import OrchestrateMaterialResponse
from brand_gen.harness.campaign_runner import run_campaign_harness
from brand_gen.harness.concurrency import run_async
from brand_gen.harness import RunEvent, BrandRun, BrandSession


class MockLM:
    def __init__(self):
        self.calls = []

    def _extract_text_content(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text") or "")
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)
        return str(content)

    def __call__(self, messages=None, **kwargs):
        if messages is None:
            messages = kwargs.get("messages")
        self.calls.append(messages)
        system_content = self._extract_text_content(messages[0]["content"])
        user_content = self._extract_text_content(messages[1]["content"])
        
        if "strategist" in system_content:
            return "# Mock Creative Thesis\nThis is a mock thesis."
        elif "art-director" in system_content:
            return json.dumps({
                "directions": [
                    {
                        "direction_id": "direction_1",
                        "name": "Editorial Restraint",
                        "visual_description": "Clean, spacious layout.",
                        "composition_rules": ["Negative space rule."]
                    }
                ]
            })
        elif "prompt-engineer" in system_content:
            return json.dumps({
                "physical_prompt": "A premium close-up shot."
            })
        elif "generator" in system_content:
            return json.dumps({
                "chosen_model": "flux-2-pro",
                "rationale": "Best model."
            })
        elif "synthesizer" in system_content:
            return json.dumps({
                "score": 4.5,
                "recommendation": "lock",
                "blocking_findings": [],
                "prose_summary": "Highly successful design direction."
            })
        elif any(c in system_content for c in ["product-truth-reviewer", "critic-composition", "critic-copy", "critic"]):
            return json.dumps({
                "score": 4,
                "rationale": "High fidelity.",
                "evidence": ["Great spacing"],
                "blocking": []
            })
        return "Default Mock Response"


class CampaignHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.brand_dir = Path(self.tmp_dir.name)
        # Create standard runs directory
        (self.brand_dir / "runs").mkdir(parents=True, exist_ok=True)
        # Create standard reviews directory
        (self.brand_dir / "reviews").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    @patch("brand_gen.scoring.config.configure_judge_lm")
    @patch("brand_gen.runtime.load_brand_memory")
    @patch("brand_gen.custom_scratchpad.load_custom_scratchpad_json")
    @patch("brand_gen.custom_scratchpad.load_custom_scratchpad_markdown")
    @patch("brand_gen.runtime.load_manifest")
    @patch("brand_gen.material_planning.build_material_plan_from_args")
    @patch("brand_gen.material_planning.save_plan_draft")
    @patch("brand_gen.material_planning.persist_plan_draft_to_blackboard")
    @patch("brand_gen.generation_flow.assemble_generation_scratchpad")
    @patch("brand_gen.generation_flow.save_generation_scratchpad")
    @patch("brand_gen.generation_flow.persist_generation_scratchpad_to_blackboard")
    @patch("brand_gen.html_share_cards.execute_html_share_card_scratchpad")
    @patch("brand_gen.generation_flow.execute_generation_scratchpad")
    @patch("brand_gen.harness.critique.panel.load_agent_prompt")
    @patch("brand_gen.harness.approvals.request_approval")
    def test_run_campaign_harness_share_card_success(
        self,
        mock_request_approval,
        mock_load_agent_prompt,
        mock_execute_gen,
        mock_execute_html,
        mock_persist_gen,
        mock_save_gen,
        mock_assemble_gen,
        mock_persist_plan,
        mock_save_plan,
        mock_build_plan,
        mock_load_manifest,
        mock_load_scratch_md,
        mock_load_scratch_json,
        mock_load_mem,
        mock_configure_judge,
    ):
        """Verify successful HTML share_card campaign run end-to-end with approval and dossiers."""
        mock_configure_judge.return_value = MockLM()
        mock_load_mem.return_value = (Path("profile.json"), Path("identity.json"), {"brand_name": "Sage"}, {"brand": {"name": "Sage"}})
        mock_load_scratch_json.return_value = {}
        mock_load_scratch_md.return_value = ""
        mock_load_agent_prompt.side_effect = lambda agent_id: f"Mock System Prompt for {agent_id}"
        mock_request_approval.return_value = True

        mock_build_plan.return_value = (None, {"material_type": "share_card", "mode": "hybrid"}, [])
        mock_save_plan.return_value = self.brand_dir / "plan_draft.json"
        mock_assemble_gen.return_value = {
            "schema_type": "generation_scratchpad",
            "material_type": "share_card",
            "workflow_mode": "hybrid",
            "render_backend": "html",
        }
        mock_save_gen.return_value = self.brand_dir / "generation_scratchpad.json"
        
        # Manifest setup
        mock_load_manifest.return_value = {
            "versions": {
                "v001": {
                    "files": ["v001-share_card.png"]
                }
            }
        }
        mock_execute_html.return_value = "v001"

        # Create dummy image file to bypass exists() check
        img_file = self.brand_dir / "v001-share_card.png"
        img_file.write_text("dummy image data")

        # Plan arguments namespace
        args = argparse.Namespace(
            material_type="share_card",
            goal="Test HTML share card",
            request="Make it look premium",
            source_version="",
            mode="hybrid",
            profile=None,
            identity=None,
        )

        res = run_async(run_campaign_harness(self.brand_dir, args))

        self.assertIsInstance(res, OrchestrateMaterialResponse)
        self.assertEqual(res.stop_reason, "lock")
        self.assertEqual(res.artifacts["version_id"], "v001")
        self.assertTrue(Path(res.artifacts["review_packet"]).exists())
        self.assertTrue(Path(res.artifacts["auto_review"]).exists())

        # Assert campaign runner session event logging worked
        runs_index = self.brand_dir / "runs" / "_index.jsonl"
        self.assertTrue(runs_index.exists())

        # Assert approval request was triggered in sync mode
        mock_request_approval.assert_called_once()
        call_args = mock_request_approval.call_args[0]
        self.assertEqual(call_args[1].trigger_name, "pre_paid_generation")
        self.assertEqual(call_args[2], "sync")

    @patch("brand_gen.scoring.config.configure_judge_lm")
    @patch("brand_gen.runtime.load_brand_memory")
    @patch("brand_gen.custom_scratchpad.load_custom_scratchpad_json")
    @patch("brand_gen.custom_scratchpad.load_custom_scratchpad_markdown")
    @patch("brand_gen.runtime.load_manifest")
    @patch("brand_gen.material_planning.build_material_plan_from_args")
    @patch("brand_gen.material_planning.save_plan_draft")
    @patch("brand_gen.material_planning.persist_plan_draft_to_blackboard")
    @patch("brand_gen.generation_flow.assemble_generation_scratchpad")
    @patch("brand_gen.generation_flow.save_generation_scratchpad")
    @patch("brand_gen.generation_flow.persist_generation_scratchpad_to_blackboard")
    @patch("brand_gen.html_share_cards.execute_html_share_card_scratchpad")
    @patch("brand_gen.generation_flow.execute_generation_scratchpad")
    @patch("brand_gen.harness.critique.panel.load_agent_prompt")
    @patch("brand_gen.harness.approvals.request_approval")
    def test_run_campaign_harness_browser_illustration_success(
        self,
        mock_request_approval,
        mock_load_agent_prompt,
        mock_execute_gen,
        mock_execute_html,
        mock_persist_gen,
        mock_save_gen,
        mock_assemble_gen,
        mock_persist_plan,
        mock_save_plan,
        mock_build_plan,
        mock_load_manifest,
        mock_load_scratch_md,
        mock_load_scratch_json,
        mock_load_mem,
        mock_configure_judge,
    ):
        """Verify successful generative browser_illustration campaign run end-to-end."""
        mock_configure_judge.return_value = MockLM()
        mock_load_mem.return_value = (Path("profile.json"), Path("identity.json"), {}, {})
        mock_load_scratch_json.return_value = {}
        mock_load_scratch_md.return_value = ""
        mock_load_agent_prompt.side_effect = lambda agent_id: f"Mock System Prompt for {agent_id}"
        mock_request_approval.return_value = True

        mock_build_plan.return_value = (None, {"material_type": "browser_illustration", "mode": "generative_explore"}, [])
        mock_save_plan.return_value = self.brand_dir / "plan_draft.json"
        mock_assemble_gen.return_value = {
            "schema_type": "generation_scratchpad",
            "material_type": "browser_illustration",
            "workflow_mode": "generative_explore",
            "render_backend": "native",
        }
        mock_save_gen.return_value = self.brand_dir / "generation_scratchpad.json"
        
        # Manifest setup
        mock_load_manifest.return_value = {
            "versions": {
                "v002": {
                    "files": ["v002-illustration.png"]
                }
            }
        }
        mock_execute_gen.return_value = "v002"

        # Create dummy image file to bypass exists() check
        img_file = self.brand_dir / "v002-illustration.png"
        img_file.write_text("dummy image data")

        # Plan arguments namespace
        args = argparse.Namespace(
            material_type="browser_illustration",
            goal="Test illustration",
            request="Make it futuristic",
            source_version="",
            mode="generative_explore",
            profile=None,
            identity=None,
        )

        res = run_async(run_campaign_harness(self.brand_dir, args))

        self.assertIsInstance(res, OrchestrateMaterialResponse)
        self.assertEqual(res.stop_reason, "lock")
        self.assertEqual(res.artifacts["version_id"], "v002")

        # Assert execute_generation_scratchpad was called (not HTML card builder)
        mock_execute_gen.assert_called_once()
        mock_execute_html.assert_not_called()

    @patch("brand_gen.scoring.config.configure_judge_lm")
    @patch("brand_gen.runtime.load_brand_memory")
    @patch("brand_gen.custom_scratchpad.load_custom_scratchpad_json")
    @patch("brand_gen.custom_scratchpad.load_custom_scratchpad_markdown")
    @patch("brand_gen.material_planning.build_material_plan_from_args")
    @patch("brand_gen.material_planning.save_plan_draft")
    @patch("brand_gen.material_planning.persist_plan_draft_to_blackboard")
    @patch("brand_gen.generation_flow.assemble_generation_scratchpad")
    @patch("brand_gen.generation_flow.save_generation_scratchpad")
    @patch("brand_gen.generation_flow.persist_generation_scratchpad_to_blackboard")
    @patch("brand_gen.harness.critique.panel.load_agent_prompt")
    @patch("brand_gen.harness.approvals.request_approval")
    def test_run_campaign_harness_approval_rejected(
        self,
        mock_request_approval,
        mock_load_agent_prompt,
        mock_persist_gen,
        mock_save_gen,
        mock_assemble_gen,
        mock_persist_plan,
        mock_save_plan,
        mock_build_plan,
        mock_load_scratch_md,
        mock_load_scratch_json,
        mock_load_mem,
        mock_configure_judge,
    ):
        """Verify that rejecting paid generation approval trigger raises RuntimeError and stops harness."""
        mock_configure_judge.return_value = MockLM()
        mock_load_mem.return_value = (Path("profile.json"), Path("identity.json"), {}, {})
        mock_load_scratch_json.return_value = {}
        mock_load_scratch_md.return_value = ""
        mock_load_agent_prompt.side_effect = lambda agent_id: f"Mock System Prompt for {agent_id}"
        
        # Refuse approval
        mock_request_approval.return_value = False

        mock_build_plan.return_value = (None, {"material_type": "share_card", "mode": "hybrid"}, [])
        mock_save_plan.return_value = self.brand_dir / "plan_draft.json"
        mock_assemble_gen.return_value = {
            "schema_type": "generation_scratchpad",
            "material_type": "share_card",
            "workflow_mode": "hybrid",
            "render_backend": "html",
        }
        mock_save_gen.return_value = self.brand_dir / "generation_scratchpad.json"

        args = argparse.Namespace(
            material_type="share_card",
            goal="Test HTML share card rejected",
            request="Make it premium",
            source_version="",
            mode="hybrid",
            profile=None,
            identity=None,
        )

        with self.assertRaises(RuntimeError) as context:
            run_async(run_campaign_harness(self.brand_dir, args))

        self.assertIn("Approval for paid generation was rejected or suspended", str(context.exception))

    @patch("brand_gen.pipeline_runner.load_manifest")
    def test_pipeline_runner_run_raises_value_error_hard_cutover(self, mock_load_manifest):
        """Verify PipelineRunner.run() raises ValueError for cut-over materials (hard block)."""
        mock_load_manifest.return_value = {}
        runner = PipelineRunner(
            brand_dir=self.brand_dir,
            profile={},
            identity={},
        )
        for mat in ["share_card", "browser_illustration"]:
            args = argparse.Namespace(
                material_type=mat,
                goal="Legacy test",
                request="Legacy test",
                mode="hybrid",
            )
            with self.assertRaises(ValueError) as context:
                runner.run(args)
            self.assertIn("is cut over to the new campaign control plane harness", str(context.exception))

    @patch("brand_gen.pipeline_runner.PipelineRunner.run")
    @patch("brand_gen.harness.campaign_runner.run_campaign_harness")
    def test_pipeline_runner_orchestrate_material_intercepts(self, mock_harness, mock_legacy_run):
        """Verify PipelineRunner.orchestrate_material() intercepts cut-over materials and returns harness response."""
        runner = PipelineRunner(
            brand_dir=self.brand_dir,
            profile={},
            identity={},
        )
        
        mock_harness_res = OrchestrateMaterialResponse(
            run_id="camp_workflow_id",
            stages_completed=["prepare", "plan", "validate", "execute", "review"],
            stop_reason="lock",
            artifacts={"version_id": "v999"},
        )
        
        async def mock_async_harness(*args, **kwargs):
            return mock_harness_res
            
        mock_harness.side_effect = mock_async_harness

        for mat in ["share_card", "browser_illustration"]:
            args = argparse.Namespace(
                material_type=mat,
                goal="Intercept test",
                request="Intercept test",
                mode="hybrid",
            )
            res = runner.orchestrate_material(args)
            self.assertEqual(res.run_id, "camp_workflow_id")
            self.assertEqual(res.stop_reason, "lock")
            self.assertEqual(res.artifacts["version_id"], "v999")
            
        # Assert legacy PipelineRunner.run was never called for either cut-over material
        mock_legacy_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
