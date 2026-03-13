import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = REPO_ROOT / 'mcp'
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from brand_iterate import (  # type: ignore
    build_iteration_memory_snippet,
    derive_copy_candidates,
    normalize_iteration_memory,
    save_iteration_memory,
)


class MessagingMemoryTests(unittest.TestCase):
    def test_normalize_iteration_memory_includes_messaging_notes(self):
        memory = normalize_iteration_memory({'messaging_notes': ['Voice should be precise.']})
        self.assertEqual(memory['messaging_notes'], ['Voice should be precise.'])

    def test_iteration_memory_snippet_surfaces_messaging_notes_for_interface_materials(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            save_iteration_memory(
                brand_dir,
                {
                    'version': 1,
                    'brand_notes': [],
                    'positive_examples': [],
                    'negative_examples': [],
                    'copy_notes': [],
                    'messaging_notes': ['Promise governance, not generic automation.'],
                    'material_notes': {},
                },
            )
            snippet = build_iteration_memory_snippet(brand_dir, 'x-feed')
            self.assertIn('Recent messaging notes:', snippet)
            self.assertIn('Promise governance, not generic automation.', snippet)

    def test_derive_copy_candidates_uses_messaging_notes_and_identity_messaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            brand_dir = Path(tmp)
            save_iteration_memory(
                brand_dir,
                {
                    'version': 1,
                    'brand_notes': [],
                    'positive_examples': [],
                    'negative_examples': [],
                    'copy_notes': ['Keep copy direct.'],
                    'messaging_notes': ['Lead with governed skills, not generic AI productivity.'],
                    'material_notes': {},
                },
            )
            profile = {'brand_name': 'Acme', 'description': 'A platform for reusable branded assets.'}
            identity = {
                'brand': {'name': 'Acme', 'summary': 'Reusable branded assets for modern teams.'},
                'messaging': {
                    'tagline': 'Reusable brand systems for modern teams',
                    'elevator': 'Acme helps communities curate, govern, and reuse AI agent skills.',
                    'voice': {'description': 'Technical, clear, and grounded.'},
                    'approved_copy_bank': {},
                },
            }
            payload = derive_copy_candidates(profile, identity, 'x-feed', goal='Explain Acme on X', brand_dir=brand_dir)
            self.assertEqual(payload['messaging']['tagline'], 'Reusable brand systems for modern teams')
            self.assertIn('Lead with governed skills, not generic AI productivity.', payload['messaging']['iteration_notes'])
            serialized = json.dumps(payload)
            self.assertIn('Reusable brand systems for modern teams', serialized)


if __name__ == '__main__':
    unittest.main()
