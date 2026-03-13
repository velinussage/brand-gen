import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / 'mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from pipeline_types import (  # type: ignore
    CritiqueChecks,
    PipelineResult,
    PlanCritique,
    PromptReview,
    PlanValidation,
    MaterialPlan,
    RouteDecision,
    WorkflowMeta,
    critique_from_dict,
    plan_draft_from_dict,
    scratchpad_from_dict,
)


class PipelineTypesTests(unittest.TestCase):
    def test_material_plan_validate_rejects_invalid_mode(self):
        plan = MaterialPlan(material_type='social', mode='weird')
        self.assertIn("Invalid mode 'weird'", plan.validate()[0])

    def test_plan_draft_converter_preserves_role_pack(self):
        typed = plan_draft_from_dict(
            {
                'plan': {
                    'material_type': 'social',
                    'mode': 'hybrid',
                    'role_pack': {
                        'selected_roles': [
                            {'role': 'composition', 'source_key': 'hero-ref', 'path': '/tmp/hero.png'}
                        ],
                        'required_roles': ['composition'],
                    },
                },
                'derived': {'missing_required_roles': []},
            },
            'test-wf',
        )
        self.assertEqual(typed.meta.workflow_id, 'test-wf')
        self.assertEqual(typed.plan.role_pack.selected_roles[0].role, 'composition')
        self.assertEqual(typed.plan.role_pack.required_roles, ['composition'])

    def test_critique_and_scratchpad_converters(self):
        critique = critique_from_dict(
            {
                'plan_validation': {'ok': False, 'errors': ['missing'], 'warnings': ['warn']},
                'prompt_review': {'issues': ['long'], 'recommendations': ['shorten']},
                'checks': {'blocking': ['fix first'], 'warnings': ['careful']},
                'plan_path': '/tmp/plan.json',
            },
            'wf-1',
        )
        self.assertTrue(critique.has_blocking)
        self.assertEqual(critique.plan_path, '/tmp/plan.json')

        scratchpad = scratchpad_from_dict(
            {
                'material_type': 'social',
                'workflow_mode': 'hybrid',
                'effective_prompt': 'prompt',
                'generation_mode': 'image',
                'execution': {'model': 'flux', 'aspect_ratio': '1:1'},
                'checks': {'blocking': ['wait'], 'warnings': ['warn']},
                'reference_context': {'passed_reference_paths': ['/tmp/ref.png']},
                'brand_dir': '/tmp/brand',
            },
            'wf-2',
        )
        self.assertTrue(scratchpad.has_blocking)
        self.assertEqual(scratchpad.execution.model, 'flux')
        self.assertEqual(scratchpad.reference_paths, ['/tmp/ref.png'])

    def test_pipeline_result_to_dict(self):
        result = PipelineResult(
            workflow_id='test-123',
            route=RouteDecision(
                meta=WorkflowMeta(workflow_id='test-123', stage='route'),
                route_key='generative_explore',
                score=0.2,
            ),
            critique=PlanCritique(
                meta=WorkflowMeta(workflow_id='test-123', stage='critique'),
                plan_validation=PlanValidation(ok=True),
                prompt_review=PromptReview(issues=[]),
                checks=CritiqueChecks(blocking=[]),
            ),
            stopped_at='complete',
            stop_reason='ok',
        )
        data = result.to_dict()
        self.assertEqual(data['workflow_id'], 'test-123')
        self.assertEqual(data['route']['route_key'], 'generative_explore')
        self.assertEqual(data['critique']['meta']['stage'], 'critique')


if __name__ == '__main__':
    unittest.main()
