import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / 'mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import brand_iterate_mcp  # type: ignore
from pipeline_runner import PipelineRunner, StageResult  # type: ignore
from pipeline_types import (  # type: ignore
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
        return StageResult(RouteDecision(meta=WorkflowMeta(self.workflow_id, 'route'), route_key='generative_explore'))

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
        result = runner.run(object())
        self.assertEqual(result.stopped_at, 'critique')
        self.assertIsNone(result.result)
        self.assertTrue(result.critique.has_blocking)

    def test_pipeline_full_run(self):
        runner = DummyRunner()
        result = runner.run(object())
        self.assertEqual(result.stopped_at, 'complete')
        self.assertEqual(result.result.version_id, 'v1')
        self.assertEqual(result.iterations, 1)

    def test_pipeline_skip_route(self):
        runner = DummyRunner(skip_route=True)
        result = runner.run(object())
        self.assertIsNone(result.route)
        self.assertEqual(result.stopped_at, 'complete')

    def test_pipeline_graceful_routing_failure(self):
        runner = DummyRunner(raise_route=True)
        result = runner.run(object())
        self.assertIsNone(result.route)
        self.assertEqual(result.stopped_at, 'complete')

    def test_pipeline_handles_stage_exception(self):
        runner = DummyRunner()

        def boom(_):
            raise RuntimeError('nope')

        runner._run_plan_draft = boom  # type: ignore
        result = runner.run(object())
        self.assertEqual(result.stopped_at, 'plan_draft')
        self.assertIn('nope', result.stop_reason)

    def test_pipeline_mcp_tool_roundtrip(self):
        fake_result = PipelineResult(workflow_id='wf-123', stopped_at='complete', stop_reason='ok')

        class FakeRunner:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, plan_args):
                return fake_result

        with patch('pipeline_runner.PipelineRunner', FakeRunner), \
             patch('brand_iterate.get_brand_dir', return_value=Path('/tmp/brand-gen')), \
             patch('brand_iterate.load_brand_memory', return_value=(None, None, {}, {})):
            output, is_error = brand_iterate_mcp.handle_tool_call('brand_pipeline', {'material_type': 'social'})

        self.assertFalse(is_error)
        payload = json.loads(output)
        self.assertEqual(payload['workflow_id'], 'wf-123')
        self.assertEqual(payload['stopped_at'], 'complete')


if __name__ == '__main__':
    unittest.main()
