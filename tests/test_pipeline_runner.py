import argparse
import io
import json
import unittest
from pathlib import Path
from contextlib import redirect_stderr
from unittest.mock import patch

from mcp import brand_iterate_mcp
from mcp.pipeline_request import PipelineRequest
from mcp.pipeline_runner import PipelineRunner, StageResult
from mcp.pipeline_types import (
    CritiqueChecks,
    GenerationResult,
    GenerationScratchpad,
    MaterialPlan,
    PipelineResult,
    PlanCritique,
    PlanDraft,
    PlanValidation,
    PromptReview,
    RouteDecision,
    WorkflowMeta,
)


class DummyRunner(PipelineRunner):
    def __init__(self, *, skip_route=False, raise_route=False, critique_blocking=False):
        super().__init__(Path('/tmp/brand-gen'), {}, {}, skip_route=skip_route)
        self.raise_route = raise_route
        self.critique_blocking = critique_blocking

    def _run_route(self, plan_args):
        if self.raise_route:
            raise RuntimeError('route failed')
        recommended = 'generative_explore'
        route_key = recommended
        method = 'predicate'
        if self.route_override and self.route_override != recommended:
            route_key = self.route_override
            method = 'user_override'
        return StageResult(RouteDecision(meta=WorkflowMeta(self.workflow_id, 'route'), route_key=route_key, method=method))

    def _run_plan_draft(self, plan_args):
        return StageResult(
            PlanDraft(
                meta=WorkflowMeta(self.workflow_id, 'plan_draft'),
                plan=MaterialPlan(material_type='social', mode='hybrid'),
                output_path='/tmp/plan.json',
            )
        )

    def _run_critique(self, draft):
        critique = PlanCritique(
            meta=WorkflowMeta(self.workflow_id, 'critique'),
            plan_validation=PlanValidation(ok=True),
            prompt_review=PromptReview(issues=[]),
            checks=CritiqueChecks(blocking=['fix it'] if self.critique_blocking else [], warnings=[]),
            output_path='/tmp/critique.json',
        )
        return StageResult(critique, proceed=not self.critique_blocking, reason='Blocking issues: fix it' if self.critique_blocking else '')

    def _run_scratchpad(self, draft, critique):
        return StageResult(
            GenerationScratchpad(
                meta=WorkflowMeta(self.workflow_id, 'scratchpad'),
                material_type='social',
                workflow_mode='hybrid',
                effective_prompt='hello',
                output_path='/tmp/scratch.json',
            )
        )

    def _run_generate(self, scratchpad):
        return StageResult(
            GenerationResult(
                meta=WorkflowMeta(self.workflow_id, 'generate'),
                version_id='v1',
                image_paths=['/tmp/v1.png'],
                scratchpad_path='/tmp/scratch.json',
                iteration=1,
                all_versions=['v1'],
            )
        )


class PipelineRunnerTests(unittest.TestCase):
    def test_pipeline_stops_at_blocking_critique(self):
        runner = DummyRunner(critique_blocking=True)
        result = runner.run(argparse.Namespace())
        self.assertEqual(result.stopped_at, 'critique')
        self.assertIsNone(result.result)
        self.assertTrue(result.critique.has_blocking)

    def test_pipeline_full_run(self):
        runner = DummyRunner()
        result = runner.run(argparse.Namespace())
        self.assertEqual(result.stopped_at, 'complete')
        self.assertEqual(result.result.version_id, 'v1')
        self.assertEqual(result.iterations, 1)

    def test_pipeline_skip_route(self):
        runner = DummyRunner(skip_route=True)
        result = runner.run(argparse.Namespace())
        self.assertIsNone(result.route)
        self.assertEqual(result.stopped_at, 'complete')

    def test_pipeline_graceful_routing_failure(self):
        runner = DummyRunner(raise_route=True)
        result = runner.run(argparse.Namespace())
        self.assertIsNone(result.route)
        self.assertEqual(result.stopped_at, 'complete')

    def test_pipeline_handles_stage_exception(self):
        runner = DummyRunner()

        def boom(_):
            raise RuntimeError('nope')

        runner._run_plan_draft = boom  # type: ignore
        result = runner.run(argparse.Namespace())
        self.assertEqual(result.stopped_at, 'plan_draft')
        self.assertIn('nope', result.stop_reason)

    def test_pipeline_can_proceed_past_blocking_critique_when_bypass_recorded(self):
        runner = PipelineRunner(Path('/tmp/brand-gen'), {}, {}, allow_blocking=True)
        draft = PlanDraft(
            meta=WorkflowMeta('wf-123', 'plan_draft'),
            plan=MaterialPlan(material_type='social', mode='hybrid'),
            output_path='/tmp/plan.json',
        )
        critique_payload = {
            "plan_validation": {"ok": True, "errors": [], "warnings": []},
            "prompt_review": {"issues": [], "recommendations": []},
            "checks": {"blocking": ["fix it"], "warnings": []},
            "critique_policy": {
                "critique_mode": "strict",
                "blocking_policy": "allow_with_recorded_bypass",
                "entrypoint": "pipeline",
                "has_blocking_issues": True,
                "blocks_generation": False,
                "bypass_requested": True,
                "bypass_recorded": True,
                "bypass_reason": "pipeline ran with --allow-blocking despite blocking critique findings.",
                "bypass_recorded_at": "2026-03-17T00:00:00",
            },
        }

        with patch('mcp.pipeline_runner.load_plan_payload', return_value=({}, {'material_type': 'social', 'mode': 'hybrid'})), \
             patch('mcp.pipeline_runner.build_plan_critique_payload', return_value=critique_payload), \
             patch('mcp.pipeline_runner.save_plan_critique', return_value=Path('/tmp/critique.json')), \
             patch('mcp.pipeline_runner.persist_plan_critique_to_blackboard', return_value=Path('/tmp/blackboard.json')), \
             patch('mcp.pipeline_runner.append_run_event', return_value=Path('/tmp/wf-123.jsonl')):
            stage = runner._run_critique(draft)

        self.assertTrue(stage.proceed)
        self.assertTrue(stage.output.has_blocking)
        self.assertTrue(stage.output.critique_policy['bypass_recorded'])

    def test_pipeline_can_treat_critique_as_advisory_when_policy_allows(self):
        runner = PipelineRunner(Path('/tmp/brand-gen'), {}, {}, critique_mode='advisory')
        draft = PlanDraft(
            meta=WorkflowMeta('wf-123', 'plan_draft'),
            plan=MaterialPlan(material_type='social', mode='hybrid'),
            output_path='/tmp/plan.json',
        )
        critique_payload = {
            "plan_validation": {"ok": True, "errors": [], "warnings": []},
            "prompt_review": {"issues": [], "recommendations": []},
            "checks": {"blocking": ["fix it"], "warnings": []},
            "critique_policy": {
                "critique_mode": "advisory",
                "blocking_policy": "report_only",
                "entrypoint": "pipeline",
                "has_blocking_issues": True,
                "blocks_generation": False,
                "bypass_requested": False,
                "bypass_recorded": False,
                "bypass_reason": "",
                "bypass_recorded_at": "",
            },
        }

        with patch('mcp.pipeline_runner.load_plan_payload', return_value=({}, {'material_type': 'social', 'mode': 'hybrid'})), \
             patch('mcp.pipeline_runner.build_plan_critique_payload', return_value=critique_payload), \
             patch('mcp.pipeline_runner.save_plan_critique', return_value=Path('/tmp/critique.json')), \
             patch('mcp.pipeline_runner.persist_plan_critique_to_blackboard', return_value=Path('/tmp/blackboard.json')), \
             patch('mcp.pipeline_runner.append_run_event', return_value=Path('/tmp/wf-123.jsonl')):
            stage = runner._run_critique(draft)

        self.assertTrue(stage.proceed)
        self.assertTrue(stage.output.has_blocking)
        self.assertEqual(stage.output.critique_policy['critique_mode'], 'advisory')

    def test_pipeline_mcp_tool_roundtrip(self):
        fake_result = PipelineResult(workflow_id='wf-123', stopped_at='complete', stop_reason='ok')

        class FakeRunner:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, plan_args):
                return fake_result

        with patch('mcp.pipeline_runner.PipelineRunner', FakeRunner), \
             patch('mcp.runtime.get_brand_dir', return_value=Path('/tmp/brand-gen')), \
             patch('mcp.runtime.load_brand_memory', return_value=(None, None, {}, {})):
            output, is_error = brand_iterate_mcp.handle_tool_call('brand_pipeline', {'material_type': 'social'})

        self.assertFalse(is_error)
        payload = json.loads(output)
        self.assertEqual(payload['workflow_id'], 'wf-123')
        self.assertEqual(payload['stopped_at'], 'complete')

    def test_run_generate_does_not_call_internal_vlm_by_default(self):
        runner = PipelineRunner(Path('/tmp/brand-gen'), {}, {}, max_iterations=2)
        scratchpad = GenerationScratchpad(
            meta=WorkflowMeta('wf-123', 'scratchpad'),
            material_type='social',
            workflow_mode='hybrid',
            effective_prompt='hello',
            output_path='/tmp/scratch.json',
        )

        with patch('mcp.pipeline_runner.load_json_file', return_value={'brand_dir': '/tmp/brand-gen', 'effective_prompt': 'hello'}), \
             patch('mcp.pipeline_runner.execute_generation_scratchpad', return_value='v1') as exec_mock, \
             patch('mcp.pipeline_runner.load_manifest', return_value={'versions': {'v1': {'files': ['v1.png'], 'auto_review_path': '/tmp/v1-auto-review.md', 'agent_review_path': '/tmp/v1-agent-review.json', 'visual_review_status': 'pending'}}}), \
             patch('mcp.pipeline_runner.run_vlm_critique') as vlm_mock:
            result = runner._run_generate(scratchpad)

        self.assertEqual(result.output.version_id, 'v1')
        self.assertEqual(result.output.agent_review_path, '/tmp/v1-agent-review.json')
        self.assertEqual(result.output.visual_review_status, 'pending')
        exec_mock.assert_called_once()
        vlm_mock.assert_not_called()

    def test_source_version_flows_through_pipeline(self):
        runner = DummyRunner()
        runner.source_version = "v005"
        result = runner.run(argparse.Namespace())
        self.assertEqual(result.source_version, "v005")
        self.assertEqual(result.branch_id, runner.workflow_id)
        self.assertEqual(result.stopped_at, "complete")

    def test_scratchpad_args_include_base_image_from_pipeline_request(self):
        runner = PipelineRunner(Path('/tmp/brand-gen'), {}, {})
        runner.pipeline_request = PipelineRequest(material_type="state-card", base_image="/tmp/base.png")
        args = runner._scratchpad_args("/tmp/plan.json", {"material_type": "state-card"})
        self.assertEqual(args.base_image, "/tmp/base.png")

    def test_critique_args_include_base_image_from_pipeline_request(self):
        runner = PipelineRunner(Path('/tmp/brand-gen'), {}, {})
        runner.pipeline_request = PipelineRequest(material_type="state-card", base_image="/tmp/base.png")
        args = runner._critique_args("/tmp/plan.json")
        self.assertEqual(args.base_image, "/tmp/base.png")

    def test_route_override_recorded_in_pipeline(self):
        runner = DummyRunner()
        runner.route_override = "reference_translate"
        result = runner.run(argparse.Namespace())
        self.assertEqual(result.stopped_at, "complete")
        # Route should reflect the override
        self.assertIsNotNone(result.route)
        self.assertEqual(result.route.route_key, "reference_translate")
        self.assertEqual(result.route.method, "user_override")

    def test_pipeline_result_includes_branch_fields(self):
        result = PipelineResult(workflow_id="wf-test", source_version="v003", branch_id="wf-test")
        d = result.to_dict()
        self.assertEqual(d["source_version"], "v003")
        self.assertEqual(d["branch_id"], "wf-test")

    def test_run_generate_calls_internal_vlm_only_when_opted_in(self):
        runner = PipelineRunner(Path('/tmp/brand-gen'), {}, {}, max_iterations=2, use_internal_vlm_critique=True)
        scratchpad = GenerationScratchpad(
            meta=WorkflowMeta('wf-123', 'scratchpad'),
            material_type='social',
            workflow_mode='hybrid',
            effective_prompt='hello',
            output_path='/tmp/scratch.json',
        )
        payload = {
            'brand_dir': '/tmp/brand-gen',
            'effective_prompt': 'hello',
            'profile_path': None,
            'identity_path': None,
        }

        with patch('mcp.pipeline_runner.load_json_file', return_value=payload), \
             patch('mcp.pipeline_runner.execute_generation_scratchpad', return_value='v1'), \
             patch('mcp.pipeline_runner.load_manifest', return_value={'versions': {'v1': {'files': ['v1.png'], 'auto_review_path': '/tmp/v1-auto-review.md'}}}), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('mcp.pipeline_runner.load_blackboard', return_value={'brand_dna': {}}), \
             patch('mcp.pipeline_runner.run_vlm_critique', return_value={'vlm_available': True, 'approved': True, 'p1': [], 'p2': [], 'p3': []}) as vlm_mock:
            result = runner._run_generate(scratchpad)

        self.assertEqual(result.output.version_id, 'v1')
        vlm_mock.assert_called_once()

    def test_notify_warns_when_stage_callback_raises(self):
        runner = PipelineRunner(
            Path('/tmp/brand-gen'),
            {},
            {},
            on_stage_complete=lambda *_: (_ for _ in ()).throw(RuntimeError('callback failed')),
        )
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            runner._notify('route', {'ok': True})
        self.assertIn('Pipeline stage callback failed for route', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
