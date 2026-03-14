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

    def test_agent_regeneration_prompt_includes_new_screen_instruction(self):
        prompt = brand_iterate.build_agent_regeneration_prompt(
            'v34',
            {
                'material_type': 'browser-illustration',
                'mode': 'hybrid',
                'aspect_ratio': '16:9',
                'model': 'nano-banana-2',
                'reference_images': ['references/v34-ref-01.png'],
                'raw_prompt': 'One calm browser illustration with a real product crop.',
                'critic_summary': {'issues': ['copy felt generic']},
            },
        )
        self.assertIn('version v34', prompt)
        self.assertIn('<NEW_SCREEN_PATH>', prompt)
        self.assertIn('browser-illustration', prompt)
        self.assertIn('compare it against v34', prompt)


    def test_compare_marks_latest_overall_when_showing_all_versions(self):
        import argparse
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            brand_dir = Path(tmpdir)
            (brand_dir / 'v1-social.png').write_bytes(b'fake')
            (brand_dir / 'v2-social.png').write_bytes(b'fake')
            output = brand_dir / 'compare.html'
            manifest = {
                'versions': {
                    'v1': {
                        'material_type': 'social',
                        'generation_mode': 'hybrid',
                        'model': 'nano-banana-2',
                        'files': ['v1-social.png'],
                    },
                    'v2': {
                        'material_type': 'social',
                        'generation_mode': 'hybrid',
                        'model': 'nano-banana-2',
                        'files': ['v2-social.png'],
                    },
                }
            }
            original_load_manifest = brand_iterate.load_manifest
            original_get_brand_dir = brand_iterate.get_brand_dir
            original_platform = brand_iterate.sys.platform
            try:
                brand_iterate.load_manifest = lambda: manifest
                brand_iterate.get_brand_dir = lambda: brand_dir
                brand_iterate.sys.platform = 'linux'
                brand_iterate.cmd_compare(argparse.Namespace(
                    versions=[],
                    favorites=False,
                    top=None,
                    latest=None,
                    all_versions=True,
                    output=str(output),
                ))
            finally:
                brand_iterate.load_manifest = original_load_manifest
                brand_iterate.get_brand_dir = original_get_brand_dir
                brand_iterate.sys.platform = original_platform

            html = output.read_text()
            self.assertIn('latest overall: v2', html)
            self.assertIn('Most recent overall', html)


if __name__ == '__main__':
    unittest.main()
