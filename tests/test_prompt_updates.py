import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / 'mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

import brand_iterate  # type: ignore


class PromptUpdateTests(unittest.TestCase):
    def test_podcast_material_uses_fallback_snippet(self):
        key, variant, snippet = brand_iterate.resolve_material_prompt_snippet({}, {}, 'podcast-cover', 'hybrid')
        self.assertEqual(key, 'podcast_cover')
        self.assertEqual(variant, 'default')
        self.assertIn('square 1:1', snippet)
        self.assertIn('thumbnail', snippet)

    def test_copy_anchor_and_image_safety_are_included_for_podcast_banner(self):
        identity = {
            'messaging': {
                'tagline': 'Governed skills for AI agents',
                'approved_copy_bank': {
                    'headlines': ['Intro to Sage'],
                    'subheadlines': ['A guided walkthrough of the protocol'],
                },
            }
        }
        payload = brand_iterate.build_effective_prompt(
            {},
            identity,
            'Podcast episode banner for Intro to Sage',
            material_type='podcast-banner',
            workflow_mode='hybrid',
            disable_brand_guardrails=False,
        )
        self.assertIn('Intro to Sage', payload['copy_anchor_snippet'])
        self.assertIn('CID strings', payload['image_safety_snippet'])
        self.assertIn('prompt metadata', payload['resolved_prompt'])


if __name__ == '__main__':
    unittest.main()
